# main2.py
import os
import sys

# Asegura que 'src' (este dir) esté en sys.path cuando ejecutas: python3 src/main2.py
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Importa tus clases reales (ajusta si tus módulos se llaman distinto)
from records.indices.btree_index import BTreeIndex
from records.indices.page_btree import Page, FixedStrCodec, Int64Codec

# ---------- Helpers ----------
def page_size_for(index) -> int:
    return Page.page_size(index.M, index.key_codec)

def file_page_count(filename: str, page_size: int) -> int:
    return 0 if not os.path.exists(filename) else os.path.getsize(filename) // page_size

def dump_index(index, title: str):
    print(f"\n=== DUMP: {title} ===")
    ps = page_size_for(index)
    n = file_page_count(index.filename, ps)
    if n == 0:
        print(" (archivo vacío)")
        return
    with open(index.filename, "rb") as f:
        for pid in range(n):
            f.seek(pid * ps)
            data = f.read(ps)
            page = Page.unpack(data, key_codec=index.key_codec, BLOCK_FACTOR=index.M)
            print(f"[pid={pid}] {page}")

def rm_if_exists(path: str):
    try: os.remove(path)
    except FileNotFoundError: pass

def records_from_keys(keys, pk_start=1000, col_name="k", pk_name="rid"):
    rid = pk_start
    for k in keys:
        yield {col_name: k, pk_name: rid}
        rid += 1

# ---------- Main ----------
def main():
    print("=== PRUEBA B+ INSERT (solo) ===")

    # --------- Caso 1: INT ----------
    idx_file_int = os.path.join(ROOT, "bplus_int.idx")
    rm_if_exists(idx_file_int)

    bplus_int = BTreeIndex(
        column_name="k",
        type="int",
        filename=idx_file_int,
        is_primary=False,
        primary_key_column="rid",
        M=4
    )

    keys_int = [45, 75, 100, 36, 120, 70, 11, 111, 47, 114, 74, 50, 52, 55, 72, 71, 60, 65, 67, 69, 68, 66, 80, 90, 0, 10, 9]

    print("\n-- Insertando INT keys:", keys_int)
    for rec in records_from_keys(keys_int, pk_start=1000, col_name="k", pk_name="rid"):
        ok = bplus_int.add(rec)
        if not ok:
            print("  ! Falló insert:", rec)

    dump_index(bplus_int, title="B+ INT (M=4)")
    bplus_int.display_pretty()

"""
    # --------- Caso 2: STR(20) ----------
    idx_file_str = os.path.join(ROOT, "bplus_str.idx")
    rm_if_exists(idx_file_str)

    bplus_str = BTreeIndex(
        column_name="name",
        type="str",
        filename=idx_file_str,
        is_primary=False,
        primary_key_column="rid",
        M=4
    )

    keys_str = [
        "ana",
        "bernardo",
        "zz-top",
        "álvaro",
        "xxxxxxxxxxxxxxxxxxxxLARGO",  # >20 bytes → se trunca
        "maria",
        "mario",
        "alberto",
        "alejandra",
        "zeta",
    ]
    print("\n-- Insertando STR keys:", keys_str)
    for rec in records_from_keys(keys_str, pk_start=2000, col_name="name", pk_name="rid"):
        ok = bplus_str.add(rec)
        if not ok:
            print("  ! Falló insert:", rec)

    dump_index(bplus_str, title="B+ STR(20) (M=4)")

    print("\nNota:")
    print("- Si tu implementación encadena hojas, revisa 'next_page' en páginas Leaf.")
    print("- Verás las strings largas truncadas por el codec de 20 bytes.")
    print("- Deben aparecer páginas Internal si los splits se hicieron bien.")
"""

if __name__ == "__main__":
    main()
