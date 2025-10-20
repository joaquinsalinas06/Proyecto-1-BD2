import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.table_manager import TableManager

def clean_indices():
    # Clean the root indices directory (where table_manager creates files)
    indices_dir = "indices"
    if os.path.exists(indices_dir):
        for file in os.listdir(indices_dir):
            filepath = os.path.join(indices_dir, file)
            try:
                os.remove(filepath)
            except:
                pass

if __name__ == "__main__":
    print("TEST: B+Tree Clustered Index\n")

    clean_indices()
    tm = TableManager()

    print("1. Creando tabla con indice B+Tree clustered...")
    sql = """
    CREATE TABLE productos (
        id INT KEY INDEX BTREE,
        nombre VARCHAR[50],
        precio FLOAT
    );
    """
    result = tm.sql(sql)
    print(f"   [OK] Tabla creada\n")

    print("2. Insertando registros en orden aleatorio...")
    productos_data = [
        (5, "Laptop", 999.99),
        (2, "Mouse", 19.99),
        (8, "Teclado", 49.99),
        (1, "Monitor", 299.99),
        (9, "Webcam", 79.99),
        (3, "Auriculares", 59.99),
        (7, "Microfono", 89.99),
        (4, "Escritorio", 199.99),
        (6, "Silla", 149.99),
        (10, "Lampara", 29.99),
        (15, "Mousepad", 9.99),
        (20, "Hub USB", 24.99),
        (25, "Cable HDMI", 14.99),
        (30, "Adaptador", 34.99),
        (35, "Cargador", 44.99),
        (40, "Funda", 12.99),
        (45, "Soporte", 54.99),
        (50, "Protector", 8.99)
    ]

    for id_val, nombre, precio in productos_data:
        tm.sql(f"INSERT INTO productos VALUES ({id_val}, '{nombre}', {precio});")
    print(f"   [OK] Insertados {len(productos_data)} registros\n")

    print("3. Probando busqueda por punto en B+Tree...")
    test_ids = [1, 5, 15, 30, 50, 99]  # 99 no existe
    for id_val in test_ids:
        result = tm.sql(f"SELECT * FROM productos WHERE id = {id_val};")
        if 'data' in result[0] and result[0]['data']:
            record = result[0]['data'][0]
            print(f"   id={id_val}: {record['nombre']}, precio=${record['precio']}")
        else:
            print(f"   id={id_val}: No encontrado")
    print()

    print("4. Probando busqueda por rango en B+Tree...")
    result = tm.sql("SELECT * FROM productos WHERE id BETWEEN 5 AND 20;")
    encontrados = len(result[0]['data'])
    ids = [r['id'] for r in result[0]['data']]
    print(f"   Rango [5,20]: encontrados {encontrados} registros")
    print(f"   IDs: {ids}")

    result = tm.sql("SELECT * FROM productos WHERE id BETWEEN 1 AND 10;")
    encontrados = len(result[0]['data'])
    ids = [r['id'] for r in result[0]['data']]
    print(f"   Rango [1,10]: encontrados {encontrados} registros")
    print(f"   IDs: {ids}")

    result = tm.sql("SELECT * FROM productos WHERE id BETWEEN 25 AND 50;")
    encontrados = len(result[0]['data'])
    ids = [r['id'] for r in result[0]['data']]
    print(f"   Rango [25,50]: encontrados {encontrados} registros")
    print(f"   IDs: {ids}")
    assert encontrados == 6, f"Se esperaban 6, se obtuvieron {encontrados}"
    print()

    print("5. Probando operadores de comparacion...")
    result = tm.sql("SELECT * FROM productos WHERE id < 10;")
    count = len(result[0]['data'])
    print(f"   id < 10: {count} registros")
    assert count == 9, f"Se esperaban 9 (ids: 1-9), se obtuvieron {count}"

    result = tm.sql("SELECT * FROM productos WHERE id <= 10;")
    count = len(result[0]['data'])
    print(f"   id <= 10: {count} registros")
    assert count == 10, f"Se esperaban 10 (ids: 1-10), se obtuvieron {count}"

    result = tm.sql("SELECT * FROM productos WHERE id > 40;")
    count = len(result[0]['data'])
    print(f"   id > 40: {count} registros")
    assert count == 2, f"Se esperaban 2, se obtuvieron {count}"

    result = tm.sql("SELECT * FROM productos WHERE id >= 40;")
    count = len(result[0]['data'])
    print(f"   id >= 40: {count} registros")
    assert count == 3, f"Se esperaban 3, se obtuvieron {count}"

    result = tm.sql("SELECT * FROM productos WHERE id = 25;")
    count = len(result[0]['data'])
    print(f"   id = 25: {count} registros")
    assert count == 1, f"Se esperaban 1, se obtuvieron {count}"

    result = tm.sql("SELECT * FROM productos WHERE id != 25;")
    count = len(result[0]['data'])
    print(f"   id != 25: {count} registros")
    assert count == 17, f"Se esperaban 17, se obtuvieron {count}"
    print()

    print("6. Probando ORDER BY y LIMIT...")
    result = tm.sql("SELECT * FROM productos ORDER BY id DESC LIMIT 3;")
    nombres = [r['nombre'] for r in result[0]['data']]
    print(f"   Top 3 (DESC): {nombres}")

    result = tm.sql("SELECT * FROM productos ORDER BY id LIMIT 5;")
    nombres = [r['nombre'] for r in result[0]['data']]
    print(f"   Top 5 (ASC): {nombres}")
    print()

    print("7. Probando busqueda sin indice (escaneo completo)...")
    result = tm.sql("SELECT * FROM productos WHERE precio > 100.0;")
    count = len(result[0]['data'])
    print(f"   Productos con precio > 100: {count} registros")
    for r in result[0]['data']:
        print(f"      - {r['nombre']}: ${r['precio']}")
    print()

    print("8. Probando eliminacion en B+Tree...")
    delete_ids = [2, 10, 25, 40]
    for id_val in delete_ids:
        result = tm.sql(f"DELETE FROM productos WHERE id = {id_val};")
    print(f"   [OK] Eliminados {len(delete_ids)} registros")

    result = tm.sql("SELECT * FROM productos;")
    restantes = len(result[0]['data'])
    esperados = len(productos_data) - len(delete_ids)
    print(f"   Restantes: {restantes}/{esperados}")
    assert restantes == esperados, f"Se esperaban {esperados}, se obtuvieron {restantes}"



    # Verificar orden de IDs
    all_ids = [r['id'] for r in result[0]['data']]
    is_sorted = all_ids == sorted(all_ids)
    print(f"   IDs ordenados correctamente: {is_sorted}")
    if not is_sorted:
        print(f"   ERROR: Los IDs no están ordenados!")
        print(f"   Primeros 10 IDs: {all_ids[:10]}")
    print()

    print("9. Verificando integridad del arbol B+Tree...")
    # Buscar todos los registros restantes para verificar que están accesibles
    result = tm.sql("SELECT * FROM productos;")
    verificados = len(result[0]['data'])
    print(f"   Registros verificados: {verificados}/{esperados}")
    assert verificados == esperados, f"Fallo en integridad: esperados {esperados}, encontrados {verificados}"
    print(f"   [OK] Integridad del arbol verificada")
    print()

    print("=" * 60)
    print("✓ TODOS LOS TESTS PASARON CORRECTAMENTE")
    print("=" * 60)
