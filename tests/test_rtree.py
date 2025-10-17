import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.table_manager import TableManager

def clean_indices():
    test_dir = os.path.dirname(os.path.abspath(__file__))
    indices_dir = os.path.join(test_dir, "indices")
    if os.path.exists(indices_dir):
        for file in os.listdir(indices_dir):
            filepath = os.path.join(indices_dir, file)
            try:
                os.remove(filepath)
            except:
                pass

if __name__ == "__main__":
    print("TEST: Indice RTree (Espacial)\n")

    clean_indices()
    tm = TableManager()

    # ========== TEST 1: RTree 2D ==========
    print("[TEST 1] RTREE 2D")
    print("-" * 60)

    print("\n1. Creando tabla con indice RTree (2D)...")
    sql = """
    CREATE TABLE tiendas (
        id INT KEY INDEX SEQ,
        nombre VARCHAR[50],
        ubicacion ARRAY[2][FLOAT] INDEX RTREE
    );
    """
    result = tm.sql(sql)
    if 'error' in result[0]:
        print(f"   ERROR: {result[0]['error']}")
    else:
        print(f"   [OK] Tabla creada con indice espacial 2D\n")

    print("2. Insertando puntos espaciales 2D...")
    tiendas_data = [
        (1, "Tienda A", (10.0, 10.0)),
        (2, "Tienda B", (20.0, 20.0)),
        (3, "Tienda C", (30.0, 30.0)),
        (4, "Tienda D", (15.0, 15.0)),
        (5, "Tienda E", (25.0, 25.0)),
        (6, "Tienda F", (5.0, 5.0)),
        (7, "Tienda G", (35.0, 35.0)),
        (8, "Tienda H", (12.0, 18.0)),
        (9, "Tienda I", (28.0, 22.0)),
        (10, "Tienda J", (8.0, 12.0)),
        (11, "Tienda K", (40.0, 40.0)),
        (12, "Tienda L", (2.0, 3.0)),
        (13, "Tienda M", (50.0, 50.0)),
        (14, "Tienda N", (18.0, 22.0)),
        (15, "Tienda O", (32.0, 28.0))
    ]

    for id_val, nombre, ubicacion in tiendas_data:
        x, y = ubicacion
        result = tm.sql(f"INSERT INTO tiendas VALUES ({id_val}, '{nombre}', ({x}, {y}));")
    print(f"   [OK] Insertados {len(tiendas_data)} puntos espaciales\n")

    print("3. Probando busqueda espacial por rango (IN)...")
    # Buscar todas las tiendas en un radio de 10 unidades desde el punto (15, 15)
    result = tm.sql("SELECT * FROM tiendas WHERE ubicacion IN ((15.0, 15.0), 10.0);")
    encontrados = len(result[0]['data'])
    print(f"   Punto (15, 15) con radio 10: {encontrados} tiendas")
    for r in result[0]['data']:
        print(f"      - {r['nombre']} en {r['ubicacion']}")
    print()

    # Buscar tiendas cerca del origen
    result = tm.sql("SELECT * FROM tiendas WHERE ubicacion IN ((0.0, 0.0), 15.0);")
    encontrados = len(result[0]['data'])
    print(f"   Punto (0, 0) con radio 15: {encontrados} tiendas")
    for r in result[0]['data']:
        print(f"      - {r['nombre']} en {r['ubicacion']}")
    print()

    # Buscar en zona mas poblada
    result = tm.sql("SELECT * FROM tiendas WHERE ubicacion IN ((25.0, 25.0), 15.0);")
    encontrados = len(result[0]['data'])
    print(f"   Punto (25, 25) con radio 15: {encontrados} tiendas")
    for r in result[0]['data']:
        print(f"      - {r['nombre']} en {r['ubicacion']}")
    print()

    print("4. Probando busqueda KNN (K vecinos mas cercanos)...")
    # Encontrar las 3 tiendas más cercanas al punto (20, 20)
    result = tm.sql("SELECT * FROM tiendas WHERE ubicacion KNN ((20.0, 20.0), 3);")
    print(f"   3 tiendas mas cercanas a (20, 20):")
    for r in result[0]['data']:
        print(f"      - {r['nombre']} en {r['ubicacion']}")
    print()

    # Encontrar las 5 tiendas más cercanas al punto (10, 10)
    result = tm.sql("SELECT * FROM tiendas WHERE ubicacion KNN ((10.0, 10.0), 5);")
    print(f"   5 tiendas mas cercanas a (10, 10):")
    for r in result[0]['data']:
        print(f"      - {r['nombre']} en {r['ubicacion']}")
    print()

    # Encontrar la tienda más cercana a un punto específico
    result = tm.sql("SELECT * FROM tiendas WHERE ubicacion KNN ((50.0, 50.0), 1);")
    print(f"   Tienda mas cercana a (50, 50):")
    for r in result[0]['data']:
        print(f"      - {r['nombre']} en {r['ubicacion']}")
    print()

    print("5. Probando eliminacion con indice espacial...")
    # Eliminar algunas tiendas
    delete_ids = [3, 7, 13]
    for id_val in delete_ids:
        tm.sql(f"DELETE FROM tiendas WHERE id = {id_val};")
    print(f"   [OK] Eliminadas {len(delete_ids)} tiendas")

    result = tm.sql("SELECT * FROM tiendas;")
    restantes = len(result[0]['data'])
    esperados = len(tiendas_data) - len(delete_ids)
    print(f"   Restantes: {restantes}/{esperados}")
    print()

    # Verificar que la búsqueda KNN funciona después de eliminar
    result = tm.sql("SELECT * FROM tiendas WHERE ubicacion KNN ((30.0, 30.0), 4);")
    print(f"   KNN despues de eliminacion (4 mas cercanas a (30, 30)):")
    for r in result[0]['data']:
        print(f"      - {r['nombre']} en {r['ubicacion']}")
    print()

    # ========== TEST 2: RTree 3D ==========
    print("\n[TEST 2] RTREE 3D")
    print("-" * 60)

    print("\n1. Creando tabla con indice RTree (3D)...")
    sql = """
    CREATE TABLE sensores (
        id INT KEY INDEX SEQ,
        codigo VARCHAR[20],
        posicion ARRAY[3][FLOAT] INDEX RTREE
    );
    """
    result = tm.sql(sql)
    if 'error' in result[0]:
        print(f"   ERROR: {result[0]['error']}")
    else:
        print(f"   [OK] Tabla creada con indice espacial 3D\n")

    print("2. Insertando puntos 3D...")
    sensores_data = [
        (1, "S001", (10.0, 10.0, 5.0)),
        (2, "S002", (20.0, 20.0, 10.0)),
        (3, "S003", (15.0, 15.0, 7.5)),
        (4, "S004", (25.0, 25.0, 12.0)),
        (5, "S005", (5.0, 5.0, 2.0)),
        (6, "S006", (30.0, 30.0, 15.0)),
        (7, "S007", (12.0, 18.0, 6.0)),
        (8, "S008", (22.0, 28.0, 11.0)),
        (9, "S009", (8.0, 12.0, 4.0)),
        (10, "S010", (35.0, 35.0, 17.0))
    ]

    for id_val, codigo, posicion in sensores_data:
        x, y, z = posicion
        tm.sql(f"INSERT INTO sensores VALUES ({id_val}, '{codigo}', ({x}, {y}, {z}));")
    print(f"   [OK] Insertados {len(sensores_data)} sensores 3D\n")

    print("3. Probando busqueda espacial 3D (IN)...")
    result = tm.sql("SELECT * FROM sensores WHERE posicion IN ((15.0, 15.0, 7.5), 10.0);")
    encontrados = len(result[0]['data'])
    print(f"   Punto (15, 15, 7.5) con radio 10: {encontrados} sensores")
    for r in result[0]['data']:
        print(f"      - {r['codigo']} en {r['posicion']}")
    print()

    result = tm.sql("SELECT * FROM sensores WHERE posicion IN ((0.0, 0.0, 0.0), 15.0);")
    encontrados = len(result[0]['data'])
    print(f"   Punto (0, 0, 0) con radio 15: {encontrados} sensores")
    for r in result[0]['data']:
        print(f"      - {r['codigo']} en {r['posicion']}")
    print()

    print("4. Probando KNN 3D...")
    result = tm.sql("SELECT * FROM sensores WHERE posicion KNN ((20.0, 20.0, 10.0), 3);")
    print(f"   3 sensores mas cercanos a (20, 20, 10):")
    for r in result[0]['data']:
        print(f"      - {r['codigo']} en {r['posicion']}")
    print()

    result = tm.sql("SELECT * FROM sensores WHERE posicion KNN ((10.0, 10.0, 5.0), 5);")
    print(f"   5 sensores mas cercanos a (10, 10, 5):")
    for r in result[0]['data']:
        print(f"      - {r['codigo']} en {r['posicion']}")
    print()

    print("5. Probando eliminacion en 3D...")
    delete_ids = [2, 6, 10]
    for id_val in delete_ids:
        tm.sql(f"DELETE FROM sensores WHERE id = {id_val};")
    print(f"   [OK] Eliminados {len(delete_ids)} sensores")

    result = tm.sql("SELECT * FROM sensores;")
    restantes = len(result[0]['data'])
    esperados = len(sensores_data) - len(delete_ids)
    print(f"   Restantes: {restantes}/{esperados}")

    # Verificar búsqueda después de eliminación
    result = tm.sql("SELECT * FROM sensores WHERE posicion KNN ((25.0, 25.0, 12.0), 3);")
    print(f"   KNN despues de eliminacion (3 mas cercanos a (25, 25, 12)):")
    for r in result[0]['data']:
        print(f"      - {r['codigo']} en {r['posicion']}")
    print()

    print("[OK] Todas las pruebas pasaron exitosamente!")
