import os
import sys

# Asegura que 'src' esté en sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from records.indices.bptree_clustered_index import BTreeIndex
from records.indices.page_btree_clustered import Page
from parser.ast import ColumnDef, DataType  # asumiendo estos nombres

# ---------- Helpers ----------
def page_size_for(index) -> int:
    # el índice ya calcula y expone page_size
    return index.page_size

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
            page = Page.unpack(
                data=data,
                key_codec=index.key_codec,
                BLOCK_FACTOR=index.M,
                RECORD_SIZE=index.RECORD_SIZE,
                table_schema=index.table_schema,
            )
            # print(f"[pid={pid}] {page}")

def rm_if_exists(path: str):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass

def records_from_keys(keys, pk_start=1000, col_name="k", pk_name="rid"):
    rid = pk_start
    for k in keys:
        # DynamicRecord exige todas las columnas del schema
        yield {col_name: k, pk_name: rid}
        rid += 1
def _get_pks(res):
    return [d.get("primary_key") for d in (res or [])]

# ---------- Main ----------
# ---------- Main ----------
def main():
    print("=== PRUEBA B+ INSERT (solo) ===")

    # ---- schema mínimo: columna indexada + pk ----
    table_schema_int = [
        ColumnDef(name="k",   data_type=DataType.INT),
        ColumnDef(name="rid", data_type=DataType.INT),
    ]

    # --------- Caso 1: índice clustered por RID ----------
    idx_file_int = os.path.join(ROOT, "bplus_int.idx")
    rm_if_exists(idx_file_int)

    bplus_int = BTreeIndex(
        column_name="rid",            # índice sobre 'rid' (clustered)
        table_schema=table_schema_int,
        filename=idx_file_int,
        is_primary=True,
        primary_key_column="rid",
        M=4,
    )

    import random

    # PKs base
    pk_int = [45, 75, 100, 36, 120, 70, 11, 111, 47, 114, 74, 50, 52, 55, 72, 71,
            60, 65, 67, 69, 68, 66, 80, 90, 0, 10, 9]

    N_RANDOM = 300
    random.seed(42) 

    exist = set(pk_int)
    target_range = range(1, 10000)  
    extra = []
    if 300 not in exist:
        extra.append(300)
        exist.add(300)

    # Completa hasta N_RANDOM aleatorios únicos
    candidates = [x for x in target_range if x not in exist]
    need = N_RANDOM - len(extra)
    extra.extend(random.sample(candidates, need))

    # Concatena: primero los originales, luego los nuevos (300 incluido)
    all_pks = pk_int + extra

    print("\n-- Insertando INT PKs (incluye 300 y 299 aleatorias más) --")
    for pk in all_pks:
        rec = {"k": 0, "rid": pk}  # DynamicRecord requiere todas las columnas del schema
        ok = bplus_int.add(rec)
        if not ok:
            print("  ! Falló insert:", rec)
        print(f"\nINSERTANDO: {pk}")


    dump_index(bplus_int, title="B+ INT (M=4)")
    # bplus_int.display_pretty()
    # bplus_int.display_range(0, 10000)

    must_hits = [min(all_pks), 300, max(all_pks)] if all_pks else []
    must_hits = [pk for pk in must_hits if pk in set(all_pks)]  # por si acaso
    for pk in must_hits:
        res = bplus_int.search(pk)
        pks = _get_pks(res)
        assert len(pks) == 1 and pks[0] == pk, f"search({pk}) falló: {pks}"
        print(f"search({pk}) OK -> {pks}")

    # misses
    miss_candidates = [-1, (max(all_pks) + 1) if all_pks else 999999]
    for pk in miss_candidates:
        res = bplus_int.search(pk)
        pks = _get_pks(res)
        assert pks == [], f"search({pk}) debería ser vacío: {pks}"
        print(f"search({pk}) OK -> vacío")

    print("\nRANGE SEARCH\n")
    print(bplus_int.rangeSearch(0, 100))
if __name__ == "__main__":
    main()

