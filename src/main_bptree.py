import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from records.indices.bptree_clustered_index import BTreeIndex
from records.indices.page_btree_clustered import Page
from parser.ast import ColumnDef, DataType 


# ---------- helpers ----------
def load_csv_with_pandas(path: str):
    import pandas as pd
    df = pd.read_csv(path, dtype={"id": "int64", "name": "string", "age": "int64"})
    df["name"] = df["name"].fillna("").str.strip()
    return df.to_dict(orient="records")

def file_page_count(filename: str, page_size: int) -> int:
    return 0 if not os.path.exists(filename) else os.path.getsize(filename) // page_size

def dump_index(index, title: str):
    print(f"\n=== DUMP: {title} ===")
    ps = index.page_size
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
            print(f"[pid={pid}] {page}")

def _pks(res):
    return [d.get("primary_key") for d in (res or [])]

# ---------- main ----------
def main():
    print("=== B+ clustered por id: carga CSV con pandas ===")

    # schema: id (PK/index), name (VARCHAR fijo), age (INT)
    table_schema = [
        ColumnDef(name="id",   data_type=DataType.INT),
        ColumnDef(name="name", data_type=DataType.VARCHAR, size=20),
        ColumnDef(name="age",  data_type=DataType.INT),
    ]

    csv_path = os.path.join(ROOT, "data.csv") 
    rows = load_csv_with_pandas(csv_path)

    # archivo del índice
    idx_file = os.path.join(ROOT, "bplus_id.idx")
    try: os.remove(idx_file)
    except FileNotFoundError: pass

    # crea índice clustered por 'id'
    bplus = BTreeIndex(
        column_name="id",
        table_schema=table_schema,
        filename=idx_file,
        is_primary=True,
        primary_key_column="id",
        M=4,
    )

    # INSERT
    print(f"-- Insertando {len(rows)} filas del CSV --")
    for r in rows:
        ok = bplus.add({"id": int(r["id"]), "name": str(r["name"]), "age": int(r["age"])})
        if not ok:
            print("  ! Falló insert:", r)

    bplus.display_pretty()
    #dump_index(bplus, "B+ INT (M=4)")

    # SEARCH (clustered: sin duplicados)
    print("\n-- PRUEBA: search() --")
    for k in [45, 0, 120, 9]:
        res = bplus.search(k)
        pks = _pks(res)
        print(f"search({k}) -> {pks}")
    for k in [-1, 999]:
        res = bplus.search(k)
        pks = _pks(res)
        print(f"search({k}) -> {pks} (esperado vacío)")

    # RANGE SEARCH
    print("\n-- PRUEBA: rangeSearch() --")
    print("rangeSearch(10, 80) ->", _pks(bplus.rangeSearch(10, 80)))
    print("rangeSearch(36, 36) ->", _pks(bplus.rangeSearch(36, 36)))

    # DELETE y revalidación básica
    print("\n-- PRUEBA: remove() --")
    for k in [36, 74, 7, 10, 0, 9, 11]:
        bplus.remove(k)
        print(f"remove({k})")
        print("  search ->", _pks(bplus.search(k)))
    
    bplus.display_pretty()

    print("\n-- display_range(0, 130) --")
    bplus.display_range(0, 130)

    print("\n-- display_ALL_RECORDS --")
    print(bplus.getAllRecords())

if __name__ == "__main__":
    main()
