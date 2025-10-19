import time
import sys
import csv
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from src.table_manager import TableManager

def run_benchmark():
    print("\n" + "="*80)
    print("Benchmark 02: Games - Índice ISAM")
    print("="*80)
    
    datasets = [
        ("data/benchmarks/games_1k.csv", "1K"),
        ("data/benchmarks/games_10k.csv", "10K"),
        ("data/benchmarks/games_100k.csv", "100K")
    ]
    
    all_results = []
    
    for csv_path, size_label in datasets:
        print(f"\nProbando con {size_label} registros: {csv_path}\n")
        
        tm = TableManager()
        table_name = f"games_isam_{size_label.lower()}"
        
        start = time.time()
        query = f"CREATE TABLE {table_name} FROM FILE '{csv_path}' USING PRIMARY INDEX ISAM(AppID), INDEX HASH(Name);"
        print(f"[1/4] Carga masiva")
        print(f"   {query}")
        tm.sql(query)
        bulk_time = time.time() - start
        print(f"   ✓ {bulk_time:.2f}s\n")
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        test_id = rows[100]['AppID']
        test_name = rows[100]['Name'].replace("'", "''")
        
        start = time.time()
        query = f"SELECT * FROM {table_name} WHERE AppID = {test_id};"
        print(f"[2/4] Búsqueda por clave primaria")
        print(f"   {query}")
        result = tm.sql(query)
        pk_time = time.time() - start
        print(f"   Encontrados: {len(result[0]['data'])} registros")
        print(f"   ✓ {pk_time*1000:.2f}ms\n")
        
        start = time.time()
        query = f"SELECT * FROM {table_name} WHERE Name = '{test_name}';"
        print(f"[3/4] Búsqueda por índice hash")
        print(f"   {query[:60]}...")
        result = tm.sql(query)
        hash_time = time.time() - start
        print(f"   Encontrados: {len(result[0]['data'])} registros")
        print(f"   ✓ {hash_time*1000:.2f}ms\n")
        
        start = time.time()
        query = f"SELECT * FROM {table_name} WHERE Price BETWEEN 10 AND 50;"
        print(f"[4/4] Búsqueda por rango")
        print(f"   {query}")
        result = tm.sql(query)
        range_time = time.time() - start
        print(f"   Encontrados: {len(result[0]['data'])} registros")
        print(f"   ✓ {range_time*1000:.2f}ms")
        
        print("\n" + "─"*80)
        print(f"Resumen {size_label}:")
        print(f"  Carga masiva: {bulk_time:.2f}s")
        print(f"  Búsqueda PK:  {pk_time*1000:.2f}ms")
        print(f"  Búsqueda hash: {hash_time*1000:.2f}ms")
        print(f"  Rango de precio: {range_time*1000:.2f}ms")
        print("─"*80)
        
        all_results.append({
            'size': size_label,
            'bulk': bulk_time,
            'pk': pk_time*1000,
            'hash': hash_time*1000,
            'range': range_time*1000
        })
    
    print("\n" + "="*80)
    print("Comparación Final - ISAM")
    print("="*80)
    print(f"{'Tamaño':<10} {'Carga(s)':<12} {'PK(ms)':<12} {'Hash(ms)':<12} {'Rango(ms)':<12}")
    print("─"*80)
    for r in all_results:
        print(f"{r['size']:<10} {r['bulk']:<12.2f} {r['pk']:<12.2f} {r['hash']:<12.2f} {r['range']:<12.2f}")
    print("="*80)
    
    return all_results

if __name__ == "__main__":
    run_benchmark()
