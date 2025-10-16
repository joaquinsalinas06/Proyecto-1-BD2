from __future__ import annotations
import os
import struct
import hashlib
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar, Deque, List, Dict, Any, Protocol
from collections import deque
from records.indices.base_index import BaseIndex
from .page_btree import Page, Int64Codec, FixedStrCodec

@dataclass
class ExtractionResult():
    key: Any = None 
    right_tree: Optional[int] = -1
    left_tree: Optional[int] = -1

class BTreeIndex(BaseIndex):
    def __init__(self, 
                 column_name: str, 
                 type: str = "str",
                 filename: str = None, 
                 is_primary: bool = False, 
                 primary_key_column: str = None, 
                 M: int = 4
                 ):
        
        if M < 3:
            raise ValueError("M must be greater than 2")

        super().__init__(column_name, filename, is_primary, primary_key_column)

        if type == "int":
            self.key_codec = Int64Codec()
        elif type == "str":
            self.key_codec = FixedStrCodec(size=20)
        else:
            raise ValueError(f"type not soported: {type}")

        self.root_page = -1
        self.M: int = M

        self.page_size = Page.page_size(self.M, self.key_codec)

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
        
        sec_val = self._canon(record[self.column_name])
        pk_val  = int(record[self.primary_key_column])
        
        if not os.path.exists(self.filename):
            with open(self.filename, 'wb') as file:
                root_page = Page(block_factor=self.M, key_codec=self.key_codec, is_leaf=True)
                root_page.keys[0] = sec_val
                root_page.count = 1
                root_page.refs[0] = pk_val
                file.write(root_page.pack())
            self.root_page = 0
            return True
    
        split_result = self._insert(id=self.root_page, key=sec_val, ref=pk_val)

        if split_result is not None:
            parent = Page(block_factor=self.M, key_codec=self.key_codec, is_leaf=False)
            parent.keys[0] = split_result.key
            parent.children[0] = self.root_page
            parent.children[1] = split_result.right_tree
            parent.count = 1
            self.root_page = self._append_page(parent)
        
        return True
    
    def remove(self, key: Any) -> bool:
        
        if self.root_page == -1:
            return True
        
        self._remove(self.root_page, key)

        root = self._get_page_by_id(self.root_page)

        if root and root.count == 0:
            self.root_page = root.children[0]

        if root.count == 0:
            self.root_page == -1

        return True

    def getAllRecords(self) -> List[Dict[str, Any]]:
        """Returns all records (stub - not implemented)"""
        return []

    def clear_all(self) -> int:
        """Clears all records (stub - not implemented)"""
        return 0
    
    def display_pretty(self) -> None:
        if self._page_count() == 0 or self.root_page == -1:
            print("(árbol vacío)")
            return
        self._display_tree(self.root_page, indent="", last=True)

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
            split_result = self._insert(node.children[i], key, ref=ref)
            if split_result is not None:
                if node.count < self.M - 1:
                    self._relocate_right(node, split_result.key, ref, split_result.right_tree)
                    self._set_page_by_id(node, id)
                elif self.M % 2 == 0:
                    return self._split_par(node=node, key=split_result.key, id=id, ref=ref, right_tree=split_result.right_tree)
                else:
                    return self._split_impar(node, split_result.key, split_result.right_tree)
        
        return None
    
    def _split_par(self, 
                   node: Page, 
                   key: Any, 
                   id: int, # reference in index.dat
                   ref: int, #pk
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
        
        right_node = Page(block_factor=self.M, key_codec=self.key_codec, is_leaf=node.is_leaf)
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
                        ref: int = -1,
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
        
    def _get_page_by_id(self, pid: int) -> Page:
        ps = self.page_size
        with open(self.filename, "rb") as f:
            f.seek(pid * ps)
            data = f.read(ps)
        if len(data) != ps:
            raise EOFError(f"incomplete page: pid={pid}, got={len(data)}, expected={ps}")
        return Page.unpack(data, key_codec=self.key_codec, BLOCK_FACTOR=self.M)

    def _set_page_by_id(self, page: Page, pid: int) -> int:
        blob = page.pack()
        mode = 'r+b' if os.path.exists(self.filename) else 'wb'
        with open(self.filename, mode) as f:
            f.seek(pid * self.page_size)
            f.write(blob)
        return pid
    
    def _page_count(self) -> int:
        try:
            return os.path.getsize(self.filename) // self.page_size
        except FileNotFoundError:
            return 0

    def _append_page(self, page: Page) -> int:
        pid = self._page_count()
        return self._set_page_by_id(page, pid)

    def _canon(self, v):
        return self.key_codec.from_bin(self.key_codec.to_bin(v))

    def _display_tree(self, pid: int, indent: str, last: bool) -> None:
        page = self._get_page_by_id(pid)
        branch = "└" if last else "├"
        keys_str = ",".join(str(k) for k in page.keys[:page.count])
        tag = " L" if page.is_leaf else ""
        print(f"{indent}{branch}[{keys_str}]{tag} (pid={pid})")

        if not page.is_leaf:
            child_indent = indent + ("  " if last else "│ ")
            child_ids = page.children[:page.count + 1]
            for i, cid in enumerate(child_ids):
                if cid == -1:
                    continue
                self._display_tree(cid, child_indent, last=(i == len(child_ids) - 1))

    def display_levels(self) -> None:
        if self._page_count() == 0:
            print("(árbol vacío)")
            return

        from collections import deque
        q = deque([(self.root_page, 0)])
        cur_level = 0
        line = []

        def flush(level):
            if line:
                print(f"Nivel {level}: " + "   ||   ".join(line))

        while q:
            pid, level = q.popleft()
            if level != cur_level:
                flush(cur_level)
                line = []
                cur_level = level

            page = self._get_page_by_id(pid)
            keys_str = ",".join(str(k) for k in page.keys[:page.count])
            node_tag = "L" if page.is_leaf else "I"
            line.append(f"({node_tag}, pid={pid})[{keys_str}]")

            if not page.is_leaf:
                for cid in page.children[:page.count + 1]:
                    if cid != -1:
                        q.append((cid, level + 1))

        flush(cur_level)

    def _remove(self, 
                id: int, 
                key: Any
                ) -> None:
        
        node = self._get_page_by_id(id)

        i = 0
        while i < node.count and key > node.keys[i]:
            i += 1

        if node.is_leaf:
            if i < node.count and node.keys[i] == key:
                self._pop_element(node, i)
                self._set_page_by_id(node, id)
            return

        self._remove(node.children[i], key)

        left_id  = node.children[i-1] if i > 0 else -1
        cur_id   = node.children[i]
        right_id = node.children[i+1] if i < node.count else -1

        nc_iminus = self._get_page_by_id(left_id)  if left_id  != -1 else None
        nc_i      = self._get_page_by_id(cur_id)   if cur_id   != -1 else None
        nc_iplus  = self._get_page_by_id(right_id) if right_id != -1 else None

        if nc_i.count < (self.M - 1) // 2:
            # rotación con izquierdo
            if i > 0 and nc_iminus.count > (self.M - 1) // 2:
                if nc_iminus.is_leaf:
                    self._pop_element(nc_iminus, nc_iminus.count - 1)
                    self._set_page_by_id(nc_iminus, left_id)
                # falta verificar si despues del pop queda vacio
                extract_result = self._extract_last(nc_iminus)
                self._relocate_left(node=nc_i, key=node.keys[i - 1], left_tree=extract_result.right_tree)
                node.keys[i - 1] = extract_result.key

                self._set_page_by_id(node, id)
                self._set_page_by_id(nc_i, cur_id)
            # rotación con derecho
            elif i < node.count and nc_iplus.count > (self.M - 1) // 2:
                extract_result = self._extract_first(nc_iplus)
                
                if (nc_i.is_leaf):
                    self._relocate_right(nc_i, extract_result.key, node.refs[i], right_tree=extract_result.left_tree)
                else:
                    self._relocate_right(nc_i, node.keys[i], node.refs[i], right_tree=extract_result.left_tree)
                node.keys[i] = extract_result.key
                if not node.is_leaf and not nc_i.is_leaf:
                    for idx in range(len(nc_i.keys)):
                        if(nc_i.keys[idx] == key):
                            ncc_idx = self._get_page_by_id(nc_i.children[idx])
                            nc_i.keys[idx] = self._max_key(ncc_idx)
                            break

                self._set_page_by_id(node, id)                
                self._set_page_by_id(nc_i, cur_id)
                self._set_page_by_id(nc_iplus, right_id)
            # join con izquierdo
            elif i > 0:

                self._join(nc_iminus, node.keys[i - 1], nc_i)
                deleted_node_id = node.children[i]
                nc_i.deleted = -1
                node.children[i] = -1
                self._pop_element(node, i - 1)

                self._set_page_by_id(node, id)
                self._set_page_by_id(nc_i, cur_id)
                self._set_page_by_id(nc_iminus, left_id)

                i = i - 1
            # join con derecho
            else:
                self._join(nc_i, node.keys[i], nc_iplus)
                nc_iplus.deleted = -1
                node.children[i + 1] = -1
                self._pop_element(node, i)
                if not node.is_leaf and not nc_i.is_leaf:
                    for idx in range(len(nc_i.keys)):
                        if(nc_i.keys[idx] == key):
                            ncc_idx = self._get_page_by_id(nc_i.children[idx])
                            nc_i.keys[idx] = self._max_key(ncc_idx)
                            break  
                self._set_page_by_id(node, id)
                self._set_page_by_id(nc_i, cur_id)
                self._set_page_by_id(nc_iplus, right_id)

        
        if i < node.count and node.keys[i] == key:
            nc_i = self._get_page_by_id(node.children[i])
            key = self._max_key(nc_i)
            node.keys[i] = key
            self._set_page_by_id(node, id)            

    def _pop_element(self, 
                     node: Page, 
                     pos: int
                     ) -> None:
        i = pos
        while i < node.count - 1:
            node.keys[i] = node.keys[i + 1]
            node.children[i + 1] = node.children[i + 2]
            i += 1
        node.count -= 1

    def _extract_last(self, 
                      node: Page
                    ) -> ExtractionResult:
        result = ExtractionResult()
        result.key = node.keys[node.count - 1]
        result.right_tree = node.children[node.count]
        if (not node.is_leaf):
            node.count -= 1
        return result

    def _extract_first(self, 
                       node: Page
                       ) -> ExtractionResult:
        result = ExtractionResult()
        result.key = node.keys[0]
        result.left_tree = node.children[0]
        i = 0
        while i < node.count - 1:
            node.keys[i] = node.keys[i + 1]
            node.children[i] = node.children[i + 1]
            i += 1
        node.children[i] = node.children[i + 1]
        node.count -= 1
        return result
    
    def _relocate_left(self, 
                       node: Page, 
                       key: Any, 
                       left_tree: int=-1
                       ) -> None:
        i = node.count - 1
        while i >= 0 and key < node.keys[i]:
            node.keys[i + 1] = node.keys[i]
            node.children[i + 2] = node.children[i + 1]
            i -= 1
        node.children[i + 2] = node.children[i + 1]
        i += 1
        node.keys[i] = key
        node.children[i] = left_tree
        node.count += 1

    def _max_key(self, 
                 node: Page
                 ) -> Any:
        while not node.is_leaf:
            node = self._get_page_by_id(node.children[node.count])
        return node.keys[node.count-1] 
    
    def _join(self, 
              left_node: Page, 
              middle: Any, 
              right_node: Page
              ) -> None:

        if not left_node.is_leaf:
            self._relocate_right(left_node, middle, right_tree=right_node.children[0])

        for i in range(right_node.count):
            self._relocate_right(left_node, right_node.keys[i], right_tree=right_node.children[i + 1])

