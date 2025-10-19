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
            if file.endswith('.dat'):
                filepath = os.path.join(indices_dir, file)
                try:
                    os.remove(filepath)
                except:
                    pass

if __name__ == "__main__":
    print("TEST: Índice Extendible ISAM")
    
    clean_indices()
    tm = TableManager()
    
    print("1. Creando tabla con índice ISAM...")
    sql = """
    CREATE TABLE usuarios (
        id INT KEY INDEX ISAM,
        nombre VARCHAR[50] ,
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
    
    


