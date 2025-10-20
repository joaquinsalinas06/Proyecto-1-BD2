"""
Benchmark 01: Airbnb BpTree File Index + R-Tree
Tests query patterns on Airbnb dataset with R-Tree spatial index
"""
import time
import sys
import shutil
import csv
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.table_manager import TableManager
from benchmarks.benchmark_helper import print_io_stats, capture_io_stats

def insert_row_dict(tm, table_name, row_dict):
    values = []
    for key, value in row_dict.items():
        if value is None or value == '':
            values.append("NULL")
        elif isinstance(value, (int, float)):
            values.append(str(value))
        else:
            str_value = str(value)
            if str_value.replace('.', '').replace('-', '').isdigit():
                values.append(str_value)
            elif str_value.startswith('(') and str_value.endswith(')'):
                values.append(str_value)
            elif str_value.startswith('[') and str_value.endswith(']'):
                values.append(str_value)
            else:
                safe_value = str_value.replace("'", "''")
                values.append(f"'{safe_value}'")
    
    values_str = ', '.join(values)
    query = f"INSERT INTO {table_name} VALUES ({values_str});"
    return tm.sql(query)


def print_step_header(step_num, total_steps, title):
    print(f"\n{'='*80}")
    print(f"[{step_num}/{total_steps}] {title}")
    print(f"{'='*80}")


def run_benchmark():
    print("BENCHMARK 01: AIRBNB - BpTree FILE INDEX + R-TREE")

    datasets = [
        ("data/benchmarks/airbnb_1k.csv", "1K"),
        ("data/benchmarks/airbnb_10k.csv", "10K"),
        ("data/benchmarks/airbnb_100k.csv", "100K"),
    ]

    all_results = []

    for csv_path, size_label in datasets:
        print(f"\n{'='*80}")
        print(f"📊 Dataset: {size_label} registros desde {csv_path}")
        print(f"{'='*80}")

        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            all_rows = [row for row in reader if row.get('id')]
        
        total_records = len(all_rows)
        bulk_count = int(total_records * 0.9) # El 90% para carga masiva
        
        bulk_data = all_rows[:bulk_count]
        insert_data = all_rows[bulk_count:bulk_count + 100]  #
        
        test_ids_for_search = [row['id'] for row in bulk_data[bulk_count-20:bulk_count]]
        test_ids_for_delete = [row['id'] for row in insert_data[:20]]

        test_locations = []
        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('location'):
                    try:
                        location_str = row['location'].strip()
                        if location_str.startswith('(') and location_str.endswith(')'):
                            coords = location_str[1:-1].split(',')
                            if len(coords) == 2:
                                lat = float(coords[0].strip())
                                lon = float(coords[1].strip())
                                test_locations.append((lat, lon))
                                if len(test_locations) >= 3:
                                    break
                    except:
                        continue
        
        table_name = f"airbnb_bptree_{size_label.lower()}"

        try:
            import glob
            
            if Path(f"indices/{table_name}").exists():
                shutil.rmtree(f"indices/{table_name}")
            
            for idx_file in glob.glob(f"indices/{table_name}_*.*"):
                try:
                    Path(idx_file).unlink()
                except:
                    pass

            metadata_path = Path("indices/tables_metadata.json")
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    tables_to_remove = [k for k in metadata.keys() if k.startswith('airbnb_bptree_')]
                    for tbl in tables_to_remove:
                        if tbl in metadata:
                            del metadata[tbl]
                    
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=2)
                except:
                    pass

            tm = TableManager()

            print_step_header(1, 10, "CREAR TABLA Y CARGA MASIVA")
            temp_bulk_csv = f"data/benchmarks/.temp_bulk_{size_label}.csv"
            with open(temp_bulk_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=bulk_data[0].keys())
                writer.writeheader()
                writer.writerows(bulk_data)
            
            start = time.time()
            create_sql = f"CREATE TABLE {table_name} FROM FILE '{temp_bulk_csv}' USING PRIMARY INDEX BTREE(id), INDEX RTREE(location);"
            print(f"   📝 {create_sql}")
            tm.sql(create_sql)
            
            bulk_load_time = time.time() - start
            print(f"   ✓ {bulk_count} registros cargados en {bulk_load_time:.4f}s ({bulk_count/bulk_load_time:.2f} rec/s)")
    
            Path(temp_bulk_csv).unlink(missing_ok=True)

            print_step_header(2, 10, "INSERCIONES INDIVIDUALES")
            insert_times = []
            
            tm.reset_io_stats(table_name)
            
            for i, row in enumerate(insert_data, 1):
                start = time.time()
                insert_row_dict(tm, table_name, row)
                insert_times.append(time.time() - start)

            avg_insert = sum(insert_times) / len(insert_times) if insert_times else 0
            print(f"   ✓ Tiempo promedio de inserción: {avg_insert*1000:.4f}ms ({len(insert_data)} inserciones)")
            
            print_io_stats(tm, table_name, "Inserciones", len(insert_data))
            insert_io_stats = capture_io_stats(tm, table_name)

            print_step_header(3, 10, "BÚSQUEDA EXACTA POR CLAVE PRIMARIA (id)")
            print(f"   ✅ Índice BpTree optimiza búsquedas exactas")
            
            exact_times = []
            total_exact_results = 0
            
            tm.reset_io_stats(table_name)
            
            for i, test_id in enumerate(test_ids_for_search[:10], 1):
                start = time.time()
                query = f"SELECT * FROM {table_name} WHERE id = {test_id};"
                result = tm.sql(query)
                exact_times.append(time.time() - start)
                num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                total_exact_results += num_results

            avg_exact = sum(exact_times) / len(exact_times) if exact_times else 0
            print(f"   ✓ Tiempo promedio: {avg_exact*1000:.4f}ms | {len(test_ids_for_search[:10])} búsquedas exactas")
            
            print_io_stats(tm, table_name, "Búsqueda Exacta", 10)
            exact_io_stats = capture_io_stats(tm, table_name)

            print_step_header(4, 10, "CONSULTAS ESPACIALES DE RANGO (IN) - Ubicación dentro del radio")
            print(f"   ✅ Índice R-Tree optimiza búsquedas espaciales")
            
            spatial_in_times = []
            total_spatial_in_results = 0

            tm.reset_io_stats(table_name)
            
            rad = [0.01, 0.05, 0.1]
            query_count = 0
            
            for loc in test_locations:
                for radius in rad:
                    query_count += 1
                    start = time.time()
                    query = f"SELECT * FROM {table_name} WHERE location IN (({loc[0]}, {loc[1]}), {radius});"
                    result = tm.sql(query)
                    spatial_in_times.append(time.time() - start)
                    num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                    total_spatial_in_results += num_results
                    
            avg_spatial_in = sum(spatial_in_times) / len(spatial_in_times) if spatial_in_times else 0
            avg_spatial_in_results = total_spatial_in_results / len(spatial_in_times) if spatial_in_times else 0
            print(f"   ✓ Tiempo promedio: {avg_spatial_in*1000:.4f}ms | Resultados promedio: {avg_spatial_in_results:.1f} por query")

            print_io_stats(tm, table_name, "Búsqueda Espacial IN", query_count)
            spatial_in_io_stats = capture_io_stats(tm, table_name)

            print_step_header(5, 10, "CONSULTAS ESPACIALES KNN - K vecinos más cercanos")
            print(f"   ✅ Índice R-Tree optimiza búsquedas KNN")
            
            knn_times = []
            
            k_values = [5, 10, 20]
            query_count = 0

            tm.reset_io_stats(table_name)
            
            for loc in test_locations:
                for k in k_values:
                    query_count += 1
                    start = time.time()
                    query = f"SELECT * FROM {table_name} WHERE location KNN (({loc[0]}, {loc[1]}), {k});"
                    result = tm.sql(query)
                    knn_times.append(time.time() - start)
                    num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                    
                    if query_count <= 3:
                        query_display = query if len(query) <= 80 else query[:77] + "..."
                        print(f"   📝 Query {query_count}: {query_display}")
                        print(f"      ✓ {num_results} resultados en {knn_times[-1]*1000:.2f}ms")

            avg_knn = sum(knn_times) / len(knn_times) if knn_times else 0
            print(f"   ✓ Tiempo promedio: {avg_knn*1000:.4f}ms")

            print_io_stats(tm, table_name, "Búsqueda Espacial KNN", query_count)
            knn_io_stats = capture_io_stats(tm, table_name)

            print_step_header(6, 10, "CONSULTAS POR CIUDAD")
            print(f"   Sin índice en city (escaneo completo)")
            
            test_cities = list(set([row['city'] for row in all_rows[:50] if row.get('city')]))[:5]

            city_times = []
            total_city_results = 0

            tm.reset_io_stats(table_name)

            for i, city in enumerate(test_cities, 1):
                start = time.time()
                safe_city = city.replace("'", "''")
                query = f"SELECT * FROM {table_name} WHERE city = '{safe_city}';"
                result = tm.sql(query)
                city_times.append(time.time() - start)
                num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                total_city_results += num_results
                
            avg_city = sum(city_times) / len(city_times) if city_times else 0
            print(f"   ✓ Tiempo promedio: {avg_city*1000:.4f}ms | Resultados promedio: {total_city_results/len(test_cities) if test_cities else 0:.1f}")

            print_io_stats(tm, table_name, "Búsqueda por Ciudad", len(test_cities))
            city_io_stats = capture_io_stats(tm, table_name)

            print_step_header(7, 10, "CONSULTAS DE RANGO - Precio")
            print(f"   BETWEEN sin índice en price (escaneo completo)")
            
            prices = [float(row['price']) for row in all_rows if row.get('price') and row['price'] != '']
            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 1000

            num_price_ranges = 5
            price_step = (max_price - min_price) / num_price_ranges
            price_ranges = [(min_price + i * price_step, min_price + (i + 1) * price_step) for i in range(num_price_ranges)]
            
            price_range_times = []
            total_price_results = 0

            tm.reset_io_stats(table_name)
            for idx, (low, high) in enumerate(price_ranges, 1):
                start = time.time()
                query = f"SELECT * FROM {table_name} WHERE price BETWEEN {int(low)} AND {int(high)};"
                result = tm.sql(query)
                price_range_times.append(time.time() - start)
                num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                total_price_results += num_results
                
            avg_price_range = sum(price_range_times) / len(price_range_times) if price_range_times else 0
            print(f"   ✓ Tiempo promedio: {avg_price_range*1000:.4f}ms | Resultados promedio: {total_price_results/len(price_ranges) if price_ranges else 0:.1f}")

            print_io_stats(tm, table_name, "Búsqueda por Rango de Precio", len(price_ranges))
            price_range_io_stats = capture_io_stats(tm, table_name)

            print_step_header(8, 10, "CONSULTAS DE RANGO - Clave Primaria (id)")
            print(f"   ✅ Índice BpTree permite escaneo de rangos")
            
            num_pk_ranges = 5
            sorted_keys = sorted([int(k) for k in test_ids_for_search])
            pk_range_times = []
            total_pk_results = 0

            tm.reset_io_stats(table_name)
            
            for i in range(num_pk_ranges):
                range_start = sorted_keys[i * len(sorted_keys) // num_pk_ranges]
                range_end = sorted_keys[(i + 1) * len(sorted_keys) // num_pk_ranges - 1]
                
                start = time.time()
                query = f"SELECT * FROM {table_name} WHERE id BETWEEN {range_start} AND {range_end};"
                result = tm.sql(query)
                pk_range_times.append(time.time() - start)
                num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                total_pk_results += num_results
                
                if i < 3:
                    print(f"   📝 Query {i+1}: {query}")
                    print(f"      ✓ {num_results} resultados en {pk_range_times[-1]*1000:.2f}ms")
            
            avg_pk_range = sum(pk_range_times) / len(pk_range_times) if pk_range_times else 0
            print(f"   ✓ Tiempo promedio: {avg_pk_range*1000:.4f}ms | Resultados promedio: {total_pk_results/num_pk_ranges if num_pk_ranges else 0:.1f}")

            print_io_stats(tm, table_name, "Búsqueda por Rango de PK", num_pk_ranges)
            pk_range_io_stats = capture_io_stats(tm, table_name)

            print_step_header(9, 10, "CONSULTAS POR TIPO DE HABITACIÓN")
            print(f"   Sin índice en room_type (escaneo completo)")
            
            test_room_types = list(set([row['room_type'] for row in all_rows[:50] if row.get('room_type')]))[:3]

            room_type_times = []
            total_room_type_results = 0

            tm.reset_io_stats(table_name)  # Reset I/O counters
            
            for i, room_type in enumerate(test_room_types, 1):
                start = time.time()
                safe_room_type = room_type.replace("'", "''")
                query = f"SELECT * FROM {table_name} WHERE room_type = '{safe_room_type}';"
                result = tm.sql(query)
                room_type_times.append(time.time() - start)
                num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                total_room_type_results += num_results
                
                if i <= 3:
                    print(f"   📝 Query {i}: {query}")
                    print(f"      ✓ {num_results} resultados en {room_type_times[-1]*1000:.2f}ms")

            avg_room_type = sum(room_type_times) / len(room_type_times) if room_type_times else 0
            print(f"   ✓ Tiempo promedio: {avg_room_type*1000:.4f}ms | Resultados promedio: {total_room_type_results/len(test_room_types) if test_room_types else 0:.1f}")

            print_io_stats(tm, table_name, "Búsqueda por Tipo de Habitación", len(test_room_types))
            room_type_io_stats = capture_io_stats(tm, table_name)

            print_step_header(10, 10, "OPERACIONES DE DELETE")
            
            max_delete_tests = min(20, len(test_ids_for_delete))
            delete_times = []
            delete_keys = test_ids_for_delete[:max_delete_tests]

            tm.reset_io_stats(table_name)
            for idx, key in enumerate(delete_keys, 1):
                start = time.time()
                query = f"DELETE FROM {table_name} WHERE id = {key};"
                tm.sql(query)
                delete_times.append(time.time() - start)
                
                if idx <= 3:
                    print(f"   📝 Query {idx}: {query}")
                    print(f"      ✓ Eliminado en {delete_times[-1]*1000:.2f}ms")

            avg_delete = sum(delete_times) / len(delete_times) if delete_times else 0
            print(f"   ✓ Tiempo promedio de delete: {avg_delete*1000:.4f}ms ({max_delete_tests} deletes)")

            print_io_stats(tm, table_name, "Deletes", max_delete_tests)
            delete_io_stats = capture_io_stats(tm, table_name)

            result = {
                'index': 'BpTree + R-Tree',
                'size': size_label,
                'records': total_records,
                'bulk_load_time': bulk_load_time,
                'bulk_load_rate': bulk_count/bulk_load_time if bulk_load_time > 0 else 0,
                'avg_insert': avg_insert * 1000,
                'avg_exact': avg_exact * 1000,
                'spatial_in': avg_spatial_in * 1000,
                'spatial_knn': avg_knn * 1000,
                'city_query': avg_city * 1000,
                'price_range': avg_price_range * 1000,
                'pk_range': avg_pk_range * 1000,
                'room_type_query': avg_room_type * 1000,
                'avg_delete': avg_delete * 1000,
                'insert_io': insert_io_stats,
                'exact_io': exact_io_stats,
                'spatial_in_io': spatial_in_io_stats,
                'spatial_knn_io': knn_io_stats,
                'city_io': city_io_stats,
                'price_range_io': price_range_io_stats,
                'pk_range_io': pk_range_io_stats,
                'room_type_io': room_type_io_stats,
                'delete_io': delete_io_stats,
            }
            all_results.append(result)

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                if 'tm' in locals() and hasattr(tm, 'tables') and table_name in tm.tables:
                    table = tm.tables[table_name]
                    for idx_name, idx in table.indexes.items():
                        if hasattr(idx, 'rtree_index'):
                            try:
                                idx.rtree_index.close()
                            except:
                                pass
            except:
                pass
            
            if Path(f"indices/{table_name}").exists():
                shutil.rmtree(f"indices/{table_name}")
            
            import glob
            for rtree_file in glob.glob(f"indices/{table_name}_*.dat") + glob.glob(f"indices/{table_name}_*.idx"):
                try:
                    Path(rtree_file).unlink()
                except:
                    pass

    print("\n" + "="*165)
    print("RESUMEN DE RENDIMIENTO - BpTree FILE + R-TREE INDEX")
    print("="*165)
    print(f"{'Tamaño':<10} {'Bulk Load':<15} {'Insert':<12} {'PK Exact':<12} {'Spatial IN':<15} {'Spatial KNN':<15} "
          f"{'City':<12} {'Price Range':<15} {'PK Range':<15} {'Room Type':<15} {'Delete':<12}")
    print(f"{'':10} {'(segundos)':<15} {'(ms)':<12} {'(ms)':<12} {'(ms)':<15} {'(ms)':<15} "
          f"{'(ms)':<12} {'(ms)':<15} {'(ms)':<15} {'(ms)':<15} {'(ms)':<12}")
    print("="*165)
    for r in all_results:
        print(f"{r['size']:<10} {r['bulk_load_time']:<15.4f} {r['avg_insert']:<12.4f} "
              f"{r['avg_exact']:<12.4f} {r['spatial_in']:<15.4f} {r['spatial_knn']:<15.4f} {r['city_query']:<12.4f} "
              f"{r['price_range']:<15.4f} {r['pk_range']:<15.4f} {r['room_type_query']:<15.4f} {r['avg_delete']:<12.4f}")
    print("="*165)

    print("\n" + "="*140)
    print("RESUMEN DE ESTADÍSTICAS DE I/O - BpTree FILE + R-TREE INDEX")
    print("="*140)
    print(f"{'Tamaño':<10} {'Operación':<25} {'Lecturas (páginas)':<25} {'Escrituras (páginas)':<25} {'Total I/O (páginas)':<25}")
    print("="*140)
    for r in all_results:
        io_stats = {
            'Insert': r['insert_io'],
            'Exact Search': r['exact_io'],
            'Spatial IN': r['spatial_in_io'],
            'Spatial KNN': r['spatial_knn_io'],
            'City Query': r['city_io'],
            'Price Range': r['price_range_io'],
            'PK Range': r['pk_range_io'],
            'Room Type Query': r['room_type_io'],
            'Delete': r['delete_io'],
        }
        for op_name, stats in io_stats.items():
            reads = stats.get('disk_reads', 0)
            writes = stats.get('disk_writes', 0)
            total_io = reads + writes
            print(f"{r['size']:<10} {op_name:<25} {reads:<25} {writes:<25} {total_io:<25}")

    print("\nINFORMACIÓN DE ÍNDICES:")
    print("   BpTree (id):    Búsqueda exacta y rangos")
    print("   R-Tree (location):  Consultas espaciales")
    print("="*140)

    return all_results


if __name__ == "__main__":
    run_benchmark()
