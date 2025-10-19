import time
import sys
import csv
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from src.table_manager import TableManager

def run_benchmark():
    print("\n" + "="*80)
    print("Benchmark 03: Airbnb - Índice B+Tree")
    print("="*80)
    
    datasets = [
        ("data/benchmarks/airbnb_1k.csv", "1K"),
        ("data/benchmarks/airbnb_10k.csv", "10K"),
        ("data/benchmarks/airbnb_100k.csv", "100K")
    ]
    
    all_results = []
    
    for csv_path, size_label in datasets:
        print(f"\nProbando con {size_label} registros: {csv_path}\n")
        
        tm = TableManager()
        table_name = f"airbnb_btree_{size_label.lower()}"
        
        start = time.time()
        query = f"CREATE TABLE {table_name} FROM FILE '{csv_path}' USING PRIMARY INDEX BTREE(id), INDEX RTREE(location);"
        print(f"[1/4] Carga masiva")
        print(f"   {query}")
        tm.sql(query)
        bulk_time = time.time() - start
        print(f"   ✓ {bulk_time:.2f}s\n")
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        test_id = rows[100]['id']
        test_lat = rows[100]['latitude']
        test_lon = rows[100]['longitude']
        
        start = time.time()
        query = f"SELECT * FROM {table_name} WHERE id = {test_id};"
        print(f"[2/4] Búsqueda por clave primaria")
        print(f"   {query}")
        result = tm.sql(query)
        pk_time = time.time() - start
        print(f"   Encontrados: {len(result[0]['data'])} registros")
        print(f"   ✓ {pk_time*1000:.2f}ms\n")
        
        start = time.time()
        query = f"SELECT * FROM {table_name} WHERE location IN (({test_lat}, {test_lon}), 0.05);"
        print(f"[3/4] Búsqueda espacial (radio)")
        print(f"   {query}")
        result = tm.sql(query)
        spatial_time = time.time() - start
        print(f"   Encontrados: {len(result[0]['data'])} registros")
        print(f"   ✓ {spatial_time*1000:.2f}ms\n")
        
        start = time.time()
        query = f"SELECT * FROM {table_name} WHERE price BETWEEN 50 AND 200;"
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
        print(f"  Búsqueda espacial: {spatial_time*1000:.2f}ms")
        print(f"  Rango de precio: {range_time*1000:.2f}ms")
        print("─"*80)
        
        all_results.append({
            'size': size_label,
            'bulk': bulk_time,
            'pk': pk_time*1000,
            'spatial': spatial_time*1000,
            'range': range_time*1000
        })
    
    print("\n" + "="*80)
    print("Comparación Final - B+Tree")
    print("="*80)
    print(f"{'Tamaño':<10} {'Carga(s)':<12} {'PK(ms)':<12} {'Espacial(ms)':<15} {'Rango(ms)':<12}")
    print("─"*80)
    for r in all_results:
        print(f"{r['size']:<10} {r['bulk']:<12.2f} {r['pk']:<12.2f} {r['spatial']:<15.2f} {r['range']:<12.2f}")
    print("="*80)
    
    return all_results

if __name__ == "__main__":
    run_benchmark()
