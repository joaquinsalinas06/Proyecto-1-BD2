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
    print("TEST: Índice Extendible Hash\n")
    
    clean_indices()
    tm = TableManager()
    
    print("1. Creando tabla con índice hash...")
    sql = """
    CREATE TABLE usuarios (
        id INT KEY INDEX SEQ,
        nombre VARCHAR[50] INDEX HASH,
        edad INT
    );
    """
    tm.sql(sql)
    print("   ✓ Tabla creada\n")
    
    print("2. Insertando registros (probando splits y directory doubling)...")
    test_data = [
        (1, "Ana", 25), (2, "Bruno", 30), (3, "Carlos", 28), (4, "Diana", 35),
        (5, "Elena", 22), (6, "Fernando", 40), (7, "Gabriela", 27), (8, "Hector", 33),
        (9, "Isabel", 29), (10, "Javier", 31), (11, "Karla", 26), (12, "Luis", 38),
        (13, "Maria", 24), (14, "Nicolas", 36), (15, "Olivia", 32), (16, "Pablo", 41),
        (17, "Quintana", 29), (18, "Rosa", 34), (19, "Santiago", 27), (20, "Teresa", 39),
        (21, "Ursula", 23), (22, "Victor", 37), (23, "Walter", 28), (24, "Ximena", 35),
        (25, "Yolanda", 26), (26, "Zoe", 30), (27, "Adrian", 33), (28, "Beatriz", 29),
        (29, "Cesar", 31), (30, "Daniela", 27), (31, "Eduardo", 34), (32, "Fernanda", 25),
        (33, "Guillermo", 38), (34, "Helena", 22), (35, "Ivan", 36), (36, "Julia", 28),
        (37, "Kevin", 32), (38, "Laura", 24), (39, "Manuel", 40), (40, "Natalia", 26),
        (41, "Oscar", 35), (42, "Patricia", 29), (43, "Rodrigo", 31), (44, "Sofia", 27),
        (45, "Tomas", 33), (46, "Valentina", 25), (47, "William", 37), (48, "Yasmin", 30),
        (49, "Zaira", 28), (50, "Alberto", 34)
    ]
    
    for id_val, nombre, edad in test_data:
        tm.sql(f"INSERT INTO usuarios VALUES ({id_val}, '{nombre}', {edad});")
    print(f"   ✓ Insertados {len(test_data)} registros\n")
    
    print("3. Probando búsqueda por punto...")
    test_ids = [1, 10, 20, 30, 40, 50]
    for id_val in test_ids:
        result = tm.sql(f"SELECT * FROM usuarios WHERE id = {id_val};")
        if result[0]['data']:
            record = result[0]['data'][0]
            print(f"   id={id_val}: {record['nombre']}, edad={record['edad']}")
    
    result = tm.sql("SELECT * FROM usuarios WHERE nombre = 'Ana';")
    print(f"   Búsqueda hash (nombre='Ana'): encontrados {len(result[0]['data'])} registro(s)")
    
    result = tm.sql("SELECT * FROM usuarios WHERE nombre = 'Sofia';")
    print(f"   Búsqueda hash (nombre='Sofia'): encontrados {len(result[0]['data'])} registro(s)")
    print()
    
    print("4. Probando búsqueda por rango...")
    print("   Intentando rango en índice hash (debería fallar):")
    try:
        result = tm.sql("SELECT * FROM usuarios WHERE nombre BETWEEN 'Ana' AND 'Carlos';")
        print(f"   ⚠ ADVERTENCIA: Búsqueda por rango funcionó (cayó a escaneo completo)")
    except NotImplementedError as e:
        print(f"   ✓ Excepción esperada: {e}")
    
    print("   Rango en índice primario (debería funcionar):")
    result = tm.sql("SELECT * FROM usuarios WHERE id BETWEEN 10 AND 20;")
    encontrados = len(result[0]['data'])
    print(f"   Rango [10,20]: encontrados {encontrados} registros")
    assert encontrados == 11, f"Se esperaban 11 registros, se obtuvieron {encontrados}"
    
    result = tm.sql("SELECT * FROM usuarios WHERE id BETWEEN 25 AND 35;")
    encontrados = len(result[0]['data'])
    print(f"   Rango [25,35]: encontrados {encontrados} registros")
    assert encontrados == 11, f"Se esperaban 11 registros, se obtuvieron {encontrados}"
    print()
    
    print("5. Probando eliminación...")
    delete_ids = [5, 15, 25, 35, 45]
    for id_val in delete_ids:
        tm.sql(f"DELETE FROM usuarios WHERE id = {id_val};")
    print(f"   ✓ Eliminados {len(delete_ids)} registros")
    
    result = tm.sql("SELECT * FROM usuarios;")
    restantes = len(result[0]['data'])
    esperados = len(test_data) - len(delete_ids)
    print(f"   Restantes: {restantes}/{esperados}")
    assert restantes == esperados, f"Se esperaban {esperados} registros, se obtuvieron {restantes}"
    print()
    
    print("6. Probando valores duplicados en índice hash...")
    
    sql = """
    CREATE TABLE clientes (
        id INT KEY INDEX SEQ,
        ciudad VARCHAR[50] INDEX HASH,
        monto FLOAT
    );
    """
    tm.sql(sql)
    
    duplicados = [
        (1, "Lima", 100.0), (2, "Lima", 200.0), (3, "Lima", 150.0), (4, "Lima", 175.0),
        (5, "Cusco", 300.0), (6, "Cusco", 250.0), (7, "Cusco", 280.0),
        (8, "Arequipa", 180.0), (9, "Arequipa", 220.0), (10, "Arequipa", 195.0),
        (11, "Trujillo", 160.0), (12, "Trujillo", 190.0),
        (13, "Piura", 140.0), (14, "Piura", 170.0), (15, "Piura", 155.0),
        (16, "Chiclayo", 210.0), (17, "Iquitos", 230.0), (18, "Tacna", 165.0),
        (19, "Lima", 185.0), (20, "Cusco", 295.0)
    ]
    
    for id_val, ciudad, monto in duplicados:
        tm.sql(f"INSERT INTO clientes VALUES ({id_val}, '{ciudad}', {monto});")
    print(f"   ✓ Insertados {len(duplicados)} registros\n")
    
    print("   Probando búsquedas con duplicados:")
    result = tm.sql("SELECT * FROM clientes WHERE ciudad = 'Lima';")
    lima_count = len(result[0]['data'])
    lima_ids = [r['id'] for r in result[0]['data']]
    print(f"   Búsqueda hash (ciudad='Lima'): {lima_count} registros - IDs: {lima_ids}")
    assert lima_count == 5, f"Se esperaban 5 registros de Lima, se obtuvieron {lima_count}"
    
    result = tm.sql("SELECT * FROM clientes WHERE ciudad = 'Cusco';")
    cusco_count = len(result[0]['data'])
    cusco_ids = [r['id'] for r in result[0]['data']]
    print(f"   Búsqueda hash (ciudad='Cusco'): {cusco_count} registros - IDs: {cusco_ids}")
    assert cusco_count == 4, f"Se esperaban 4 registros de Cusco, se obtuvieron {cusco_count}"
    
    result = tm.sql("SELECT * FROM clientes WHERE ciudad = 'Arequipa';")
    arequipa_count = len(result[0]['data'])
    arequipa_ids = [r['id'] for r in result[0]['data']]
    print(f"   Búsqueda hash (ciudad='Arequipa'): {arequipa_count} registros - IDs: {arequipa_ids}")
    assert arequipa_count == 3, f"Se esperaban 3 registros de Arequipa, se obtuvieron {arequipa_count}"
    print()
    
    print("   Probando eliminación de un registro duplicado:")
    tm.sql("DELETE FROM clientes WHERE id = 2;")
    result = tm.sql("SELECT * FROM clientes WHERE ciudad = 'Lima';")
    lima_despues = len(result[0]['data'])
    print(f"   Después de eliminar id=2: {lima_despues} registros de Lima")
    assert lima_despues == 4, f"Se esperaban 4 registros de Lima, se obtuvieron {lima_despues}"
    
    tm.sql("DELETE FROM clientes WHERE id = 19;")
    result = tm.sql("SELECT * FROM clientes WHERE ciudad = 'Lima';")
    lima_final = len(result[0]['data'])
    print(f"   Después de eliminar id=19: {lima_final} registros de Lima")
    assert lima_final == 3, f"Se esperaban 3 registros de Lima, se obtuvieron {lima_final}"
    print()
    
    result = tm.sql("SELECT * FROM clientes;")
    total_final = len(result[0]['data'])
    print(f"   Total de registros restantes: {total_final}/{len(duplicados) - 2}")
    print()
    
    print("✓ Todas las pruebas pasaron exitosamente!")

