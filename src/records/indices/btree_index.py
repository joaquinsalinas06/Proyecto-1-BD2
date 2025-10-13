from __future__ import annotations
import os
import struct
import hashlib
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar, Deque, List, Dict, Any
from collections import deque
from records.indices.base_index import BaseIndex

# from .base_index import BaseIndex

BLOCK_FACTOR = 4

def hash64(s: str) -> int:
    return int.from_bytes(
        hashlib.blake2b(s.encode('utf-8'), digest_size=8).digest(),
        'little',
        signed=False
    )

@dataclass
class ExtractionResult():
    key: Any = None 
    right_tree: Optional[int] = -1
    left_tree: Optional[int] = -1

class Page:

    HEADER_FORMAT = f"<iBi{BLOCK_FACTOR}i{BLOCK_FACTOR - 1}Q{BLOCK_FACTOR - 1}i" # count, is_leaf, next, children, keys, is_leaf?
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    SIZE_OF_PAGE = HEADER_SIZE

    def __init__(self, 
                 is_leaf : bool = False,
                 next_page : int = -1
                 ):
        self.keys = [0] * (BLOCK_FACTOR - 1) # secondary 
        self.children = [-1] * BLOCK_FACTOR
        self.count = 0
        self.is_leaf = is_leaf
        self.next_page = next_page
        self.refs = [-1] * (BLOCK_FACTOR - 1) # PK

    def pack(self) -> None :
        if not (0 <= self.count <= BLOCK_FACTOR - 1):
            raise ValueError("count fuera de rango")
        return struct.pack(
            self.HEADER_FORMAT,
            self.count,
            int(self.is_leaf),
            self.next_page,
            *self.children,
            *self.keys,
            *self.refs
        )
    
    @staticmethod
    def unpack(data : bytes) -> Page:    
        tup = struct.unpack_from(Page.HEADER_FORMAT, data, 0)
        count = tup[0]
        is_leaf = tup[1]
        next_page = tup[2]
        off = 3
        children = list(tup[off : off + BLOCK_FACTOR]); off += BLOCK_FACTOR
        keys = list(tup[off : off + (BLOCK_FACTOR - 1)]); off += (BLOCK_FACTOR - 1)
        refs = list(tup[off : off + (BLOCK_FACTOR - 1)]); off += (BLOCK_FACTOR - 1)

        p = Page(is_leaf=bool(is_leaf), next_page=int(next_page))
        p.count = count
        p.children[:] = children
        p.keys[:] = keys
        p.refs[:] = refs
        return p

    def __repr__(self) -> str:
        typ = "Leaf" if self.is_leaf else "Internal"
        if self.is_leaf:
            return f"Page({typ}, count={self.count}, keys={self.keys}, refs={self.refs}, next_page={self.next_page})"
        else:
            return f"Page({typ}, count={self.count}, keys={self.keys}, children={self.children})"


class BTreeIndex(BaseIndex):
    def __init__(self, 
                 column_name: str, 
                 filename: str = None, 
                 is_primary: bool = False, 
                 primary_key_column: str = None, 
                 M: int = 4
                 ):

        super().__init__(column_name, filename, is_primary, primary_key_column)

        if M < 3:
            raise ValueError("M must be greater than 2")
        self.root_page = 0
        self.M: int = M

    def search(self, key: Any) -> List[Dict[str, Any]]:
        """
        Busca por igualdad:
        - int  -> usa el valor tal cual
        - str  -> usa self._encode_key (p.ej., hash64)  [SOLO igualdad]
        Devuelve lista de dicts: {"primary_key": pk}
        """
        out: List[Dict[str, Any]] = []

        pid = getattr(self, "root_page", None)
        if pid is None or pid < 0:
            return out

        key_code = self._encode_key(key)

        while True:
            node = self._get_page_by_id(pid)
            if node.is_leaf:
                break
            i = self._lower_bound(node.keys, node.count, key_code)
            child_pid = node.children[i]
            if child_pid is None or child_pid < 0:
                return out
            pid = child_pid

        i = self._lower_bound(node.keys, node.count, key_code)
        while True:
            while i < node.count and node.keys[i] == key_code:
                out.append({"primary_key": int(node.refs[i])})
                i += 1
            if node.next_page is None or node.next_page == -1:
                break
            nxt = self._get_page_by_id(node.next_page)
            if nxt.count == 0 or nxt.keys[0] != key_code:
                break
            node = nxt
            i = 0

        return out


    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        if getattr(self, "root_page", None) is None or self.root_page < 0:
            return []

        lo_code = self._encode_key(begin_key)
        hi_code = self._encode_key(end_key)

        if lo_code > hi_code:
            lo_code, hi_code = hi_code, lo_code

        if isinstance(begin_key, str) or isinstance(end_key, str):
            raise ValueError("rangeSearch in strings is not valid")

        out: list[dict[str, Any]] = []

        pid = self.root_page
        while True:
            node = self._get_page_by_id(pid)
            if node.is_leaf:
                break
            i = self._lower_bound(node.keys, node.count, lo_code)
            child_pid = node.children[i]
            if child_pid is None or child_pid < 0:
                # índice inconsistente
                return out
            pid = child_pid

        leaf = node
        j = self._lower_bound(leaf.keys, leaf.count, lo_code)

        while True:
            while j < leaf.count:
                k = leaf.keys[j]
                if k is None:
                    j += 1
                    continue
                if k > hi_code:
                    return out
                pk = leaf.refs[j]
                out.append({"primary_key": pk})
                j += 1

            if leaf.next_page is None or leaf.next_page == -1:
                break
            leaf = self._get_page_by_id(leaf.next_page)
            j = 0

        return out

    def add(self, record: Dict[str, Any]) -> bool:

        if self.column_name not in record or self.primary_key_column not in record:
            return False
        
        sec_val = record[self.column_name]
        pk_val = record[self.primary_key_column]
        sec_val = self._encode_key(sec_val)
        
        if not os.path.exists(self.filename):
            with open(self.filename, 'wb') as file:
                root_page = Page(is_leaf=True)
                root_page.keys[0] = sec_val
                root_page.count = 1
                root_page.refs[0] = pk_val
                file.write(root_page.pack())
            self.root_page = 0
            return True
    
        split_result = self._insert(self.root_page, sec_val, ref=pk_val)
        if ( split_result is not None ):
            parent = Page(is_leaf=False)
            parent.keys[0] = split_result.key
            parent.children[0] = self.root_page
            parent.children[1] = split_result.right_tree
            parent.count = 1
            id_parent = self._set_page_by_id(parent, self._page_count())
            self.root_page = id_parent


    def remove(self, key: Any) -> bool:
        return True

    def getAllRecords(self) -> List[Dict[str, Any]]:
        """Returns all records (stub - not implemented)"""
        return []

    def clear_all(self) -> int:
        """Clears all records (stub - not implemented)"""
        return 0
    
    # ---------------------------------
    # ||            UTILS            ||
    # ---------------------------------

    def _insert(self, 
                id: int, # id of page in index.dat
                key: Any, # secondary atr - int or str
                ref: int # PK - int
                ) -> Optional[ExtractionResult[Any]]:
        
        node = self._get_page_by_id(id)

        i = 0
        while i < node.count and key > node.keys[i]:
            i += 1

        if i < node.count and node.keys[i] == key:
            return None
        
        if node.is_leaf:
            if node.count < self.M - 1:
                self._relocate(node, key, ref)
                self._set_page_by_id(node, id)
            elif ( self.M % 2 == 0 ):
                return self._split_par(node=node, key=key, id=id, ref=ref)
            else:
                return self._split_impar(node, key)
        else:
            split_result = self._insert(node.children[i], -1, key, ref=ref)
            if split_result is not None:
                if node.count < self.M - 1:
                    self._relocate_right(node, split_result.key, ref, split_result.right_tree)
                    self._set_page_by_id(node, id)
                elif self.M % 2 == 0:
                    return self._split_par(node=node, key=split_result.key, id=id, right_tree=split_result.right_tree)
                else:
                    return self._split_impar(node, split_result.key, split_result.right_tree)
        
        return None
    
    def _split_par(self, 
                   node: Page, 
                   key: Any, 
                   id: int, # reference in index.dat
                   ref: int = -1,
                   right_tree: Optional[int] = -1,
                   ) -> ExtractionResult[Any]:
        
        m = (self.M - 1) // 2
        middle = node.keys[m]
        right_node = self._generate_right_node(node, m + 1)
        node.count = m 

        if ( key < middle ):
            if ( node.is_leaf ):
                if ( key < node.keys[m - 1] ):
                    middle = node.keys[m - 1]
                else:
                    middle = key
                right_node = self._generate_right_node(node, m)
            self._relocate_right(node, key, ref, right_tree)
        else:
            if ( node.is_leaf ):
                node.count += 1
                self._relocate_right(right_node, key, ref, right_tree)
            else:
                if key < node.keys[m + 1]:
                    middle = key
                    node.count += 1
                    right_node.children[0] = right_tree
                else:
                    middle = node.keys[m + 1]
                    m = m + 1 if ( node.is_leaf ) else m + 2
                    right_node = self._generate_right_node(node, m)
                    node.count = node.count if node.is_leaf else node.count +1
                    self._relocate_right(right_node, key, ref, right_tree)

        right_node.next_page = node.next_page
        new_id_right_node = self._set_page_by_id(right_node, self._page_count())
        node.next_page = new_id_right_node
        self._set_page_by_id(node, id)
        
        return ExtractionResult(key=middle, left_tree=-1, right_tree=new_id_right_node)

    def _split_impar(self, node: Any, key: Any, right_tree: Optional[Any] = None) -> ExtractionResult[TK]:
        m = (self.M - 1) // 2
        if key > node.keys[m]:
            right_node = self._generate_right_node(node, m + 1)
            middle = node.keys[m]
            node.count = (m + 1) if node.is_leaf else m
            self._relocate_right(right_node, key, right_tree)
        else:
            m = m - 1
            right_node = self._generate_right_node(node, m + 1)
            if key < node.keys[m]:
                middle = node.keys[m]
                node.count = (m + 1) if node.is_leaf else m
                self._relocate_right(node, key, right_tree)
            else:
                middle = key
                if node.is_leaf:
                    node.keys[m + 1] = middle  # incluir en hojas (B+)
                node.count = (m + 2) if node.is_leaf else (m + 1)
                right_node.children[0] = right_tree

        if node.is_leaf:
            right_node.next = node.next
            node.next = right_node

        return ExtractionResult(middle, None, right_node)

    def _generate_right_node(self, 
                             node: Page, 
                             start_from: int
                             ) -> Page:
        
        right_node = Page(node.is_leaf)
        i, j = start_from, 0
        while i < self.M - 1:
            right_node.keys[j] = node.keys[i]
            right_node.children[j] = node.children[i] # for ints
            right_node.refs[j] = node.refs[i] # for leafs
            i += 1
            j += 1       
        right_node.children[j] = node.children[i]
        right_node.count = j

        return right_node

    def _relocate(self, 
                  node: Page, 
                  key: Any, 
                  ref: int
                  ) -> None:
        
        i = node.count - 1
        while ( i >= 0 and key < node.keys[i] ):
            node.keys[i + 1] = node.keys[i]
            node.refs[i + 1] = node.refs[i]
            i -= 1
        i += 1
        node.keys[i] = key
        node.refs[i] = ref
        node.count += 1

    def _relocate_right(self, 
                        node: Page, 
                        key: Any, 
                        ref: int,
                        right_tree: int = -1,
                        ) -> None:
        
        i = node.count - 1
        
        while i >= 0 and key < node.keys[i]:
            node.keys[i + 1] = node.keys[i]
            node.children[i + 2] = node.children[i + 1]
            node.refs[i + 1] = node.refs[i]
            i -= 1

        i += 1
        node.keys[i] = key
        node.children[i + 1] = right_tree
        node.refs[i] = ref
        node.count += 1
    
    def _encode_key(self, val) -> int:
        if isinstance(val, int):
            return val
        return hash64(val) 
    
    def _get_page_by_id(self, idx: int) -> Page:
        offset = idx * Page.SIZE_OF_PAGE
        with open(self.filename, "rb") as f:
            f.seek(offset)          
            data = f.read(Page.SIZE_OF_PAGE)
        if len(data) < Page.SIZE_OF_PAGE:
            raise EOFError("incomplete page")
        return Page.unpack(data)

    def _set_page_by_id(self, page: Page, idx: int) -> int:
        data = page.pack()
        if len(data) != Page.SIZE_OF_PAGE:
            raise ValueError("page.pack() size mismatch")
        offset = idx * Page.SIZE_OF_PAGE
        with open(self.filename, "r+b") as f:
            f.seek(offset)          
            f.write(data)
        return idx
    
    def _page_count(self) -> int:
        size = os.path.getsize(self.filename)
        if size % Page.SIZE_OF_PAGE != 0:
            raise ValueError(f"File size: ({size}) is not a multiple of page_size ({Page.SIZE_OF_PAGE}).")
        return size // Page.SIZE_OF_PAGE
    
