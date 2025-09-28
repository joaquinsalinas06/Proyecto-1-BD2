from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar, Deque, List
from collections import deque
from node_clustered import Node, InternalNode, LeafNode

TK = TypeVar("TK")
TV = TypeVar("TV")

@dataclass
class ExtractionResult(Generic[TK, TV]):
    key: TK = None 
    right_tree: Optional[Node[TK, TV]] = None
    left_tree: Optional[Node[TK, TV]] = None


class BPlusTree(Generic[TK, TV]):
    def __init__(self, _M: int) -> None:
        if _M < 3:
            raise ValueError("M must be greater than 2")
        self.root: Optional[Node[TK, TV]] = None
        self.M: int = _M

    # ------------ main functions

    def search(self, key: TK) -> bool:
        return self._search(self.root, key) if self.root else False

    """
        insert(reg: TV) -> None
        - TV must be of type Record with attribute id as key, mandatory!!
        - Works for both even and odd M values (M >= 3)
    """
    def insert(self, reg: TV) -> None:
        
        key = reg.id

        if ( self.root is None ):
            self.root = LeafNode(self.M)
            self.root.keys[0] = key
            self.root.values[0] = reg
            self.root.count = 1
        else:
            split_result = self._insert(self.root, key, reg)
            if ( split_result is not None ):
                parent = InternalNode(self.M)
                parent.keys[0] = split_result.key
                parent.children[0] = self.root
                parent.children[1] = split_result.right_tree
                parent.count = 1
                self.root = parent

    """
        remove(key: TK) -> None
        it's not working yet!!!!!    
    """
    def remove(self, key: TK) -> None:
        if self.root is None:
            return
        self._remove(self.root, key)
        if self.root and self.root.count == 0:
            temp = self.root
            self.root = self.root.children[0]

    """
        range_search(lo: TK, hi: TK) -> List[TV]
        returns a list of TV (Records) such that lo <= key <= hi
    """

    def range_search(self, lo: TK, hi: TK) -> List[TV]:

        out: List[TV] = []
        if self.root is None:
            return out

        node = self.root
        while ( not isinstance(node, LeafNode) ):
            i = self._lower_bound(node.keys, node.count, lo)
            child = node.children[i]
            assert child is not None, "InternalNode has a None child"
            node = child

        leaf = node  # tipo: LeafNode[TK, TV]

        j = self._lower_bound(leaf.keys, leaf.count, lo)

        while ( leaf is not None ):
            while ( j < leaf.count ):
                k = leaf.keys[j]
                if k is None:
                    j += 1
                    continue
                if k > hi:
                    return out
                # lo <= k <= hi
                out.append(leaf.values[j]) 
                j += 1
            leaf = leaf.next
            j = 0
        return out

    """
        search(key: TK) -> Optional[TV]
        returns the value TV (Record) associated with key TK, or None if not found
    """
    def search(self, key: TK) -> Optional[TV]:

        node = self.root

        if node is None:
            return None

        while isinstance(node, InternalNode):
            i = self._lower_bound(node.keys, node.count, key)
            child = node.children[i]
            assert child is not None, "InternalNode has a None child"
            node = child

        i = self._lower_bound(node.keys, node.count, key)

        if i < node.count and node.keys[i] == key:
            return node.values[i]
        
        return None

    def height(self) -> int:
        if self.root is None:
            return -1
        h = 0
        node = self.root
        while ( not isinstance(node, LeafNode) ):
            node = node.children[0]  
            h += 1
        return h

    def to_string(self, sep: str = ",") -> str:
        return self._to_string(self.root, sep)

    def display_pretty(self) -> None:
        self._display_breadth(self.root)

    def display_range(self) -> None:
        
        if self.root is None:
            return
        
        current = self.root
        
        while ( not isinstance(current, LeafNode) ):
            current = current.children[0]

        while current is not None:
            current.display()
            current = current.next

    # -------- Internos --------
    def _to_string(self, node: Optional[Node[TK,TV]], sep: str) -> str:
        if node is None:
            return ""
        result = []
        i = 0
        for i in range(node.count):
            if not isinstance(node, LeafNode):
                result.append(self._to_string(node.children[i], sep))
            result.append(str(node.keys[i]) + sep)
        if not isinstance(node, LeafNode):
            result.append(self._to_string(node.children[i], sep)) 
        return "".join(result)

    def _search(self, node: Optional[Node[TK,TV]], key: TK) -> bool:
        if node is None:
            return False
        i = 0
        while i < node.count and key > node.keys[i]:
            i += 1
        if i < node.count and node.keys[i] == key:
            return True
        if isinstance(node, LeafNode):
            return False
        return self._search(node.children[i], key)

    def _insert(self,
                node: Node[TK,TV],
                key: TK,
                reg: TV 
                ) -> Optional[ExtractionResult[TK]]:

        i = 0
        while ( i < node.count and key > node.keys[i] ):
            i += 1

        if ( i < node.count and node.keys[i] == key ):
            return None
        
        if ( isinstance(node, LeafNode)):
            if ( node.count < self.M - 1 ):
                self._relocate(node, key, reg)
            else:
                return self._split_par(node, key, reg=reg)

        else:
            split_result = self._insert(node.children[i], key, reg=reg)

            if ( split_result is not None ):
                if ( node.count < self.M - 1 ):
                    self._relocate_right(node, split_result.key, split_result.right_tree)
                else:
                    return self._split_par(node, split_result.key, split_result.right_tree)
        return None

    def _relocate(self, node: Node[TK,TV], key: TK, reg: TV) -> None:
        
        i = node.count - 1
        while ( i >= 0 and key < node.keys[i] ):
            node.keys[i + 1] = node.keys[i]
            if ( isinstance(node, LeafNode) ):
                node.values[i + 1] = node.values[i]
            i -= 1
        i += 1
        node.keys[i] = key
        if ( isinstance(node, LeafNode) ):
            node.values[i] = reg
        node.count += 1

    def _relocate_right(self,
                        node: Node[TK,TV],
                        key: TK, right_tree: Optional[Node[TK,TV]],
                        reg: Optional[TV] = None
                        ) -> None:

        i = node.count - 1
        
        while i >= 0 and key < node.keys[i]:
            node.keys[i + 1] = node.keys[i]
            if ( not isinstance(node, LeafNode) ):
                node.children[i + 2] = node.children[i + 1]
            else:
                node.values[i + 1] = node.values[i]
            i -= 1

        i += 1
        node.keys[i] = key
        if ( not isinstance(node, LeafNode) ):
            node.children[i + 1] = right_tree
        else:
            node.values[i] = reg
        node.count += 1

    def _relocate_left(self, node: Node[TK,TV], key: TK, left_tree: Optional[Node[TK,TV]]) -> None:
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

    def _generate_right_node(self, 
                             node: Node[TK,TV], 
                             start_from: int
                             ) -> Node[TK,TV]:
        
        if ( isinstance(node, LeafNode) ):
            right_node = LeafNode(self.M)
        else:
            right_node = InternalNode(self.M)

        i, j = start_from, 0
        
        while i < self.M - 1:
            if node.keys[i] is not None:
                right_node.keys[j] = node.keys[i]
                if ( not isinstance(node, LeafNode)):
                    right_node.children[j] = node.children[i]
                else:
                    right_node.values[j] = node.values[i]
                j += 1
                i += 1

        if ( not isinstance(node, LeafNode)):
            right_node.children[j] = node.children[i]

        right_node.count = j

        return right_node

    def _split_par(self, 
                   node: Node[TK,TV], 
                   key: TK, 
                   right_tree: Optional[Node[TK,TV]] = None,
                   reg: Optional[TV] = None
                   ) -> ExtractionResult[TK]:
        
        m = (self.M - 1) // 2
        middle = node.keys[m]
        right_node = self._generate_right_node(node, m + 1)
        node.count = m # chech should be m+1;

        if ( key < middle ):
            if ( isinstance(node, LeafNode) ):
                if ( key < node.keys[m - 1] ):
                    middle = node.keys[m - 1]
                else:
                    middle = key
                right_node = self._generate_right_node(node, m)
            self._relocate_right(node, key, right_tree, reg)
        else:
            if ( isinstance(node, LeafNode) ):
                node.count += 1
                self._relocate_right(right_node, key, right_tree, reg)
            else:
                if m + 1 < node.count and key < node.keys[m + 1]:
                    middle = key
                    node.count += 1
                    right_node.children[0] = right_tree #cccc
                else:
                    if m + 1 < node.count:
                        middle = node.keys[m + 1]
                        m = m + 1 if ( isinstance(node, LeafNode) ) else m + 2
                        right_node = self._generate_right_node(node, m)
                        node.count = node.count if isinstance(node, LeafNode) else node.count +1
                    self._relocate_right(right_node, key, right_tree, reg)

        if ( isinstance(node, LeafNode) ):
            right_node.next = node.next
            node.next = right_node

        return ExtractionResult(key=middle, left_tree=None, right_tree=right_node)


    def _remove(self, node: Node[TK,TV], key: TK) -> None:
        i = 0
        while i < node.count and key > node.keys[i]:
            i += 1

        if isinstance(node, LeafNode):
            if i < node.count and node.keys[i] == key:
                self._pop_element(node, i)
            return

        if i < node.count and node.keys[i] == key:
            key = self._min_key(node.children[i + 1])
            node.keys[i] = key
            i = i + 1

        self._remove(node.children[i], key)

        if node.children[i].count < (self.M - 1) // 2:
            # rotación con izquierdo
            if i > 0 and node.children[i - 1].count > (self.M - 1) // 2:
                extract_result = self._extract_last(node.children[i - 1])
                self._relocate_left(node.children[i], node.keys[i - 1], extract_result.right_tree)
                node.keys[i - 1] = extract_result.key
            # rotación con derecho
            elif i < node.count and node.children[i + 1].count > (self.M - 1) // 2:
                extract_result = self._extract_first(node.children[i + 1])
                self._relocate_right(node.children[i], node.keys[i], extract_result.left_tree)
                node.keys[i] = extract_result.key
            # join con izquierdo
            elif i > 0:
                self._join(node.children[i - 1], node.keys[i - 1], node.children[i])
                node.children[i] = None
                self._pop_element(node, i - 1)
            # join con derecho
            else:
                self._join(node.children[i], node.keys[i], node.children[i + 1])
                node.children[i + 1] = None
                self._pop_element(node, i)

    def _min_key(self, node: Node[TK,TV]) -> TK:
        while not isinstance(node, LeafNode):
            node = node.children[0]  # type: ignore
        return node.keys[0]  # type: ignore

    def _extract_last(self, node: Node[TK,TV]) -> ExtractionResult[TK]:
        result = ExtractionResult[TK]()
        result.key = node.keys[node.count - 1]
        result.right_tree = node.children[node.count]
        node.count -= 1
        return result

    def _extract_first(self, node: Node[TK,TV]) -> ExtractionResult[TK]:
        result = ExtractionResult[TK]()
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

    def _pop_element(self, node: Node[TK,TV], pos: int) -> None:
        i = pos
        while i < node.count - 1:
            node.keys[i] = node.keys[i + 1]
            node.children[i + 1] = node.children[i + 2]
            i += 1
        node.count -= 1

    def _join(self, left_node: Node[TK,TV], middle: TK, right_node: Node[TK,TV]) -> None:
        self._relocate_right(left_node, middle, right_node.children[0])
        for i in range(right_node.count):
            self._relocate_right(left_node, right_node.keys[i], right_node.children[i + 1])

    def _lower_bound(self, keys: list[Optional[TK]], cnt: int, key: TK) -> int:
        """Primera posición i en [0,cnt) tal que keys[i] >= key."""
        i = 0
        while i < cnt and keys[i] is not None and keys[i] < key:
            i += 1
        return i


    # ---- printing ----
    def _display_tree(self, node: Node[TK,TV], indent: str = " ", last: bool = True) -> None:
        print(indent, end="")
        if last:
            print(chr(192), end="")
            indent += "  "
        else:
            print(chr(195), end="")
            indent += "| "
        j = 0
        print("[", end="")
        for j in range(node.count - 1):
            print(node.keys[j], end=",")
        print(node.keys[j] if node.count > 0 else "", end="")
        print("]")
        if not isinstance(node, LeafNode):
            for j in range(node.count + 1):
                self._display_tree(node.children[node.count - j], indent, j == node.count)

    def _display_breadth(self, root: Optional["Node[TK,TV]"]) -> None:
        if root is None:
            return

        h = self.height()
        q: Deque["Node[TK,TV]"] = deque([root])

        while q:
            n = len(q)
            print("n: ", n)

            print(" " * (h * self.M * 4), end="")

            for _ in range(n):
                node = q[0]
                print("[", end="")

                if isinstance(node, LeafNode):
                    for j in range(self.M - 1):
                        if j < node.count:
                            kv = f"{node.keys[j]}"
                            #kv = f"{node.keys[j]}:{node.values[j]}" # uncomment to show values too
                            endc = "," if j < node.count - 1 else ""
                            print(kv, end=endc)
                        else:
                            print("  ", end="")
                else:
                    # internos: solo keys
                    for j in range(self.M - 1):
                        if j < node.count:
                            endc = "," if j < node.count - 1 else ""
                            print(node.keys[j], end=endc)
                        else:
                            print("  ", end="")

                print("]", end="")
                print(" " * (h * self.M * 3), end="")

                q.popleft()
                if ( not isinstance(node, LeafNode) ):
                    if node.children[0] is not None:
                        q.append(node.children[0])
                    for j in range(1, node.count + 1):
                        if node.children[j] is not None:
                            q.append(node.children[j])

            print()
            h -= 1

