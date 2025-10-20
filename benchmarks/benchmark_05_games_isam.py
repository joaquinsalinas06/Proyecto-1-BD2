"""
Benchmark 04: Games Isam File Index + Hash
Tests query patterns on Games dataset with Hash secondary index
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
    """Insert a row using a dictionary"""
    values = []
    for key, value in row_dict.items():
        if value is None or value == '':
            values.append("NULL")
        elif isinstance(value, (int, float)):
            values.append(str(value))
        else:
            str_value = str(value)
            # Try to convert to number if it looks like one
            if str_value.replace('.', '').replace('-', '').isdigit():
                values.append(str_value)  # Keep as number (no quotes)
            elif str_value.startswith('(') and str_value.endswith(')'):
                values.append(str_value)
            elif str_value.startswith('[') and str_value.endswith(']'):
                values.append(str_value)
            else:
                safe_value = str_value.replace("'", "''")
                values.append(f"'{safe_value}'")
    
    values_str = ', '.join(values)
    query = f"INSERT INTO {table_name} VALUES ({values_str});"
    tm.sql(query)
 

def print_step_header(step_num, total_steps, title):
    """Print formatted step header"""
    print(f"\n{'='*80}")
    print(f"[{step_num}/{total_steps}] {title}")
    print(f"{'='*80}")


def run_benchmark():
    """Execute complete benchmark for Games dataset with Isam File + Hash"""

    print("\n" + "="*80)
    print("BENCHMARK 04: GAMES - Isam FILE INDEX + HASH")
    print("="*80)

    datasets = [
        ("data/benchmarks/games_1k.csv", "1K"),
        ("data/benchmarks/games_10k.csv", "10K"),
        ("data/benchmarks/games_100k.csv", "100K"),
    ]

    all_results = []

    for csv_path, size_label in datasets:
        print(f"\n{'='*80}")
        print(f"📊 Dataset: {size_label} registros desde {csv_path}")
        print(f"{'='*80}")

        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            all_rows = [row for row in reader if row.get('AppID')]  # Games usa 'AppID' no 'id'
        
        total_records = len(all_rows)
        bulk_count = int(total_records * 0.9) # El 90% para carga masiva
        
        bulk_data = all_rows[:bulk_count]
        insert_data = all_rows[bulk_count:bulk_count + 100]  #
        
        test_ids_for_search = [row['AppID'] for row in bulk_data[bulk_count-20:bulk_count]]
        test_ids_for_delete = [row['AppID'] for row in insert_data[:20]]

        test_names = []
        names_sample_size = 35
        for row in all_rows[:100]:
            if row.get('Name') and len(test_names) < names_sample_size:
                test_names.append(row['Name'])

        table_name = f"games_isam_{size_label.lower()}"

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
                    
                    tables_to_remove = [k for k in metadata.keys() if k.startswith('games_isam_')]
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
            create_sql = f"CREATE TABLE {table_name} FROM FILE '{temp_bulk_csv}' USING PRIMARY INDEX ISAM(AppID), INDEX HASH(Name);"
            print(f"   📝 {create_sql}")
            tm.sql(create_sql)
            
            bulk_load_time = time.time() - start
            print(f"   ✓ {bulk_count} registros cargados en {bulk_load_time:.4f}s ({bulk_count/bulk_load_time:.2f} rec/s)")
            
            # Capture bulk load I/O before reset
            bulk_load_io_stats = capture_io_stats(tm, table_name)
            
            Path(temp_bulk_csv).unlink(missing_ok=True)


            print_step_header(2, 10, "INSERCIONES INDIVIDUALES")
            insert_times = []
            
            tm.reset_io_stats(table_name)

            for i, row in enumerate(insert_data, 1):
                start = time.time()
                insert_row_dict(tm, table_name, row)
                insert_times.append(time.time() - start)
                
                if i <= 3:
                    values_preview = f"AppID={row.get('AppID', 'N/A')}, Name='{row.get('Name', 'N/A')[:20]}...'"
                    print(f"   📝 Insert {i}: INSERT INTO {table_name} VALUES ({values_preview}, ...)")
                    print(f"      ✓ Insertado en {insert_times[-1]*1000:.2f}ms")

            avg_insert = sum(insert_times) / len(insert_times) if insert_times else 0
            print(f"   ✓ Tiempo promedio de inserción: {avg_insert*1000:.4f}ms ({len(insert_data)} inserciones)")

            print_io_stats(tm, table_name, "Inserciones", len(insert_data))
            insert_io_stats = capture_io_stats(tm, table_name)
            # Add bulk_load_io to insert_io_stats for final table
            insert_io_stats['bulk_load_io'] = bulk_load_io_stats.get('total_io', 0) if bulk_load_io_stats else 0

            print_step_header(3, 10, "BÚSQUEDA EXACTA POR CLAVE PRIMARIA (AppID)")
            print(f"   ✅ Índice Isam optimiza búsquedas exactas")
            
            exact_times = []
            total_exact_results = 0

            tm.reset_io_stats(table_name)
            
            for i, test_id in enumerate(test_ids_for_search[:10], 1):  # 10 exact searches from BULK data
                start = time.time()
                query = f"SELECT * FROM {table_name} WHERE AppID = {test_id};"
                result = tm.sql(query)
                exact_times.append(time.time() - start)
                num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                total_exact_results += num_results
                
                if i <= 3:
                    print(f"   📝 Query {i}: {query}")
                    print(f"      ✓ {num_results} resultados en {exact_times[-1]*1000:.2f}ms")

            avg_exact = sum(exact_times) / len(exact_times) if exact_times else 0
            print(f"   ✓ Tiempo promedio: {avg_exact*1000:.4f}ms | {len(test_ids_for_search[:10])} búsquedas exactas")

            print_io_stats(tm, table_name, "Búsquedas exactas", len(test_ids_for_search[:10]))
            exact_io_stats = capture_io_stats(tm, table_name)


            print_step_header(4, 10, "CONSULTAS HASH - Búsqueda exacta por nombre")
            hash_times = []
            total_hash_results = 0

            tm.reset_io_stats(table_name)

            for i, name in enumerate(test_names, 1):
                start = time.time()
                safe_name = name.replace("'", "''")
                query = f"SELECT * FROM {table_name} WHERE Name = '{safe_name}';"
                result = tm.sql(query)
                hash_times.append(time.time() - start)
                num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                total_hash_results += num_results
                
                if i <= 3:
                    query_display = query if len(query) <= 80 else query[:77] + "..."
                    print(f"   📝 Query {i}: {query_display}")
                    print(f"      ✓ {num_results} resultados en {hash_times[-1]*1000:.2f}ms")

            avg_hash = sum(hash_times) / len(hash_times) if hash_times else 0
            avg_hash_results = total_hash_results / len(test_names) if test_names else 0
            print(f"   ✓ Tiempo promedio: {avg_hash*1000:.4f}ms | Resultados promedio: {avg_hash_results:.1f} por query")

            print_io_stats(tm, table_name, "Consultas Hash", len(test_names))
            hash_io_stats = capture_io_stats(tm, table_name)

            print_step_header(5, 10, "CONSULTAS POR PUBLISHER")
            print(f"   Sin índice en Publishers (escaneo completo)")
            
            test_publishers = list(set([row['Publishers'] for row in all_rows[:100] if row.get('Publishers')]))[:10]

            publisher_times = []
            total_publisher_results = 0

            tm.reset_io_stats(table_name)

            for i, publisher in enumerate(test_publishers, 1):
                start = time.time()
                safe_publisher = publisher.replace("'", "''")
                query = f"SELECT * FROM {table_name} WHERE Publishers = '{safe_publisher}';"
                result = tm.sql(query)
                publisher_times.append(time.time() - start)
                num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                total_publisher_results += num_results
                
                if i <= 3:
                    query_display = query if len(query) <= 80 else query[:77] + "..."
                    print(f"   📝 Query {i}: {query_display}")
                    print(f"      ✓ {num_results} resultados en {publisher_times[-1]*1000:.2f}ms")

            avg_publisher = sum(publisher_times) / len(publisher_times) if publisher_times else 0
            print(f"   ✓ Tiempo promedio: {avg_publisher*1000:.4f}ms | Resultados promedio: {total_publisher_results/len(test_publishers) if test_publishers else 0:.1f}")

            print_io_stats(tm, table_name, "Consultas por Publisher", len(test_publishers))
            publisher_io_stats = capture_io_stats(tm, table_name)

            print_step_header(6, 10, "CONSULTAS DE RANGO - Precio")
            print(f"   BETWEEN sin índice en Price (escaneo completo)")
            
            prices = [float(row['Price']) for row in all_rows if row.get('Price') and row['Price'] != '']
            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 100

            num_price_ranges = 5
            price_step = (max_price - min_price) / num_price_ranges
            price_ranges = [(min_price + i * price_step, min_price + (i + 1) * price_step) for i in range(num_price_ranges)]
            
            price_range_times = []
            total_price_results = 0

            tm.reset_io_stats(table_name)

            for idx, (low, high) in enumerate(price_ranges, 1):
                start = time.time()
                query = f"SELECT * FROM {table_name} WHERE Price BETWEEN {low:.2f} AND {high:.2f};"
                result = tm.sql(query)
                price_range_times.append(time.time() - start)
                num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                total_price_results += num_results
                
                if idx <= 3:
                    print(f"   📝 Query {idx}: {query}")
                    print(f"      ✓ {num_results} resultados en {price_range_times[-1]*1000:.2f}ms")

            avg_price_range = sum(price_range_times) / len(price_range_times) if price_range_times else 0
            print(f"   ✓ Tiempo promedio: {avg_price_range*1000:.4f}ms | Resultados promedio: {total_price_results/len(price_ranges) if price_ranges else 0:.1f}")

            print_io_stats(tm, table_name, "Consultas de rango por Precio", len(price_ranges))
            price_range_io_stats = capture_io_stats(tm, table_name)

            print_step_header(7, 10, "CONSULTAS DE RANGO - Clave Primaria (AppID)")
            print(f"   ✅ Índice Isam permite escaneo de rangos")
            
            num_pk_ranges = 5
            sorted_keys = sorted([int(k) for k in test_ids_for_search])
            pk_range_times = []
            total_pk_results = 0

            tm.reset_io_stats(table_name)
            
            for i in range(num_pk_ranges):
                range_start = sorted_keys[i * len(sorted_keys) // num_pk_ranges]
                range_end = sorted_keys[(i + 1) * len(sorted_keys) // num_pk_ranges - 1]
                
                start = time.time()
                query = f"SELECT * FROM {table_name} WHERE AppID BETWEEN {range_start} AND {range_end};"
                result = tm.sql(query)
                pk_range_times.append(time.time() - start)
                num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                total_pk_results += num_results
                
            avg_pk_range = sum(pk_range_times) / len(pk_range_times) if pk_range_times else 0
            print(f"   ✓ Tiempo promedio: {avg_pk_range*1000:.4f}ms | Resultados promedio: {total_pk_results/num_pk_ranges if num_pk_ranges else 0:.1f}")
            print_io_stats(tm, table_name, "Consultas de rango por AppID", num_pk_ranges)
            pk_range_io_stats = capture_io_stats(tm, table_name)

            print_step_header(8, 10, "CONSULTAS DE RANGO - Reseñas Positivas")
            print(f"   ⚠ Sin índice en Positive (escaneo completo)")
            
            positives = [int(row['Positive']) for row in all_rows if row.get('Positive') and row['Positive'].isdigit()]
            if positives:
                pos_ranges = [(0, 10), (10, 100), (100, 1000)]
            else:
                pos_ranges = []

            positive_range_times = []
            total_positive_results = 0

            tm.reset_io_stats(table_name)

            for i, (low, high) in enumerate(pos_ranges, 1):
                start = time.time()
                query = f"SELECT * FROM {table_name} WHERE Positive BETWEEN {low} AND {high};"
                result = tm.sql(query)
                positive_range_times.append(time.time() - start)
                num_results = len(result[0]['data']) if result and result[0].get('data') else 0
                total_positive_results += num_results
            
            avg_positive_range = sum(positive_range_times) / len(positive_range_times) if positive_range_times else 0
            print(f"   ✓ Tiempo promedio: {avg_positive_range*1000:.4f}ms | Resultados promedio: {total_positive_results/len(pos_ranges) if pos_ranges else 0:.1f}")

            print_io_stats(tm, table_name, "Consultas de rango por Positive", len(pos_ranges))
            positive_range_io_stats = capture_io_stats(tm, table_name)

            print_step_header(9, 10, "OPERACIONES DE DELETE")
            
            max_delete_tests = min(20, len(test_ids_for_delete))
            delete_times = []
            delete_keys = test_ids_for_delete[:max_delete_tests]

            tm.reset_io_stats(table_name)

            for idx, key in enumerate(delete_keys, 1):
                start = time.time()
                query = f"DELETE FROM {table_name} WHERE AppID = {key};"
                tm.sql(query)
                delete_times.append(time.time() - start)
                
            avg_delete = sum(delete_times) / len(delete_times) if delete_times else 0
            print(f"   ✓ Tiempo promedio de delete: {avg_delete*1000:.4f}ms ({max_delete_tests} deletes)")
    
            print_io_stats(tm, table_name, "Deletes", max_delete_tests)
            delete_io_stats = capture_io_stats(tm, table_name)

            result = {
                'index': 'Isam + Hash',
                'size': size_label,
                'records': total_records,
                'bulk_load_time': bulk_load_time,
                'bulk_load_rate': bulk_count/bulk_load_time if bulk_load_time > 0 else 0,
                'avg_insert': avg_insert * 1000,
                'avg_exact': avg_exact * 1000,
                'hash_query': avg_hash * 1000,
                'publisher_query': avg_publisher * 1000,
                'price_range': avg_price_range * 1000,
                'pk_range': avg_pk_range * 1000,
                'positive_range': avg_positive_range * 1000,
                'avg_delete': avg_delete * 1000,
                'insert_io': insert_io_stats,
                'exact_io': exact_io_stats,
                'hash_io': hash_io_stats,
                'publisher_io': publisher_io_stats,
                'price_range_io': price_range_io_stats,
                'pk_range_io': pk_range_io_stats,
                'positive_range_io': positive_range_io_stats,
                'delete_io': delete_io_stats,

            }
            all_results.append(result)

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if Path(f"indices/{table_name}").exists():
                shutil.rmtree(f"indices/{table_name}")
            
            import glob
            for idx_file in glob.glob(f"indices/{table_name}_*.dat") + glob.glob(f"indices/{table_name}_*.idx"):
                try:
                    Path(idx_file).unlink()
                except:
                    pass


    print("\n" + "="*140)
    print("RESUMEN DE RENDIMIENTO - Isam FILE + HASH INDEX")
    print("="*140)
    print(f"{'Tamaño':<10} {'Bulk Load':<15} {'Insert':<12} {'PK Exact':<12} {'Hash':<12} {'Publisher':<15} "
          f"{'Price Range':<15} {'PK Range':<15} {'Positive':<15} {'Delete':<12}")
    print(f"{'':10} {'(segundos)':<15} {'(ms)':<12} {'(ms)':<12} {'(ms)':<12} {'(ms)':<15} "
          f"{'(ms)':<15} {'(ms)':<15} {'(ms)':<15} {'(ms)':<12}")
    print("="*140)
    for r in all_results:
        print(f"{r['size']:<10} {r['bulk_load_time']:<15.4f} {r['avg_insert']:<12.4f} "
              f"{r['avg_exact']:<12.4f} {r['hash_query']:<12.4f} {r['publisher_query']:<15.4f} {r['price_range']:<15.4f} "
              f"{r['pk_range']:<15.4f} {r['positive_range']:<15.4f} {r['avg_delete']:<12.4f}")
    print("="*140)
    
    print("\n" + "="*140)
    print("RESUMEN DE ESTADÍSTICAS DE I/O - Isam FILE + HASH INDEX")
    print("="*140)

    print(f"{'Tamaño':<10} {'Bulk Load I/O':<20} {'Insert I/O':<15} {'PK Exact I/O':<15} {'Hash I/O':<15} "
          f"{'Publisher I/O':<20} {'Price Range I/O':<20} {'PK Range I/O':<20} {'Positive I/O':<20} {'Delete I/O':<15}")
    for r in all_results:
        print(f"{r['size']:<10} {r['insert_io']['bulk_load_io']:<20} {r['insert_io']['total_io']:<15} "
              f"{r['exact_io']['total_io']:<15} {r['hash_io']['total_io']:<15} {r['publisher_io']['total_io']:<20} "
              f"{r['price_range_io']['total_io']:<20} {r['pk_range_io']['total_io']:<20} "
              f"{r['positive_range_io']['total_io']:<20} {r['delete_io']['total_io']:<15}")

    print("\n📊 INFORMACIÓN DE ÍNDICES:")
    print("   ✅ Isam (AppID): Búsqueda exacta y rangos - INDEXADO")
    print("   ✅ Hash (Name):        Búsqueda exacta O(1) - INDEXADO")

    print("="*140)

    return all_results


if __name__ == "__main__":
    run_benchmark()
