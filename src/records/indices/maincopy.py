
from bplustree_clustered import BPlusTree
from dataclasses import dataclass

"""
 Just for testing with Record type!!! it can be erased
"""
@dataclass
class Record:
    id: int          
    name: str
    age: int

    def __str__(self) -> str:
        return f"{self.id}: {self.name}/{self.age}"
    __repr__ = __str__

def demo_bptree(M: int) -> None:

    print(f"\n=== Demo B+Tree (M = {M}) ===")

    bptree = BPlusTree[int,Record](M)

    l = [
        Record(45, "Ana", 23), 
        Record(75, "Luis", 30), 
        Record(100, "Marta", 22),
        Record(36, "Juan", 28), 
        Record(120, "Sofia",40),
        Record(70, "Pedro", 35),
        Record(11, "Lucia", 27),
        Record(111, "Carlos", 29),
        Record(47, "Elena", 31),
        Record(114, "Jorge", 33),
        Record(74, "Carmen", 26),
        Record(50, "Carmen", 26),
        Record(52, "Carmen", 26),
        Record(55, "Carmen", 26),
        Record(60, "Carmen", 26),
        
        ]

    # l = [45, 75, 100, 36, 120, 70, 11, 111, 47, 114, 74]

    for k in l:
        bptree.insert(k)

    print("\nRecorrido por hojas:")
    bptree.display_range()

    print("\nÁrbol (por niveles):")
    bptree.display_pretty()

    # obtener lista
    rows = bptree.range_search(47, 75)

    print("\nRange search [47, 75]:", rows)

    # Búsquedas que SI existen
    must_find = [11, 36, 45, 47, 70, 74, 75, 100, 111, 114, 120]
    for k in must_find:
        rec = bptree.search(k)
        assert rec is not None and rec.id == k, f"search({k}) falló"
    print("\nOK: búsquedas exactas")

    # Búsquedas que NO existen
    for k in [10, 46, 73, 76, 119, 121]:
        assert bptree.search(k) is None, f"search({k}) debería ser None"
    print("OK: búsquedas ausentes")


if __name__ == "__main__":
    demo_bptree(4)
