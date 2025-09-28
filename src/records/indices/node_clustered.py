
from __future__ import annotations
from typing import Generic, Optional, TypeVar, List, Union

K = TypeVar("K")
V = TypeVar("V")

Node = Union["InternalNode[K, V]", "LeafNode[K, V]"]

class InternalNode(Generic[K, V]):
    def __init__(self, 
                 M: int = 4) -> None:

        if M < 2:
            raise ValueError("M must be greater or equal than 2")

        self.count: int = 0
        self.keys: List[Optional[K]] = [None] * (M - 1)
        self.children: List[Optional[Node]] = [None] * M

class LeafNode(Generic[K, V]):

    def __init__(self, 
                 M: int = 4, 
                 _next: Optional["LeafNode[K]"] = None) -> None:

        if M < 2:
            raise ValueError("M must be greater or equal than 2")

        self.count: int = 0
        self.next: Optional["LeafNode[K]"] = _next
        self.keys: List[Optional[K]] = [None] * (M - 1)
        self.values: List[Optional[V]] = [None]*(M-1) 

    def display(self) -> None:
        pares = []
        for i in range(self.count):
            k = self.keys[i]
            v = self.values[i]
            pares.append(f"{k}:{v}")
        print(", ".join(pares))




