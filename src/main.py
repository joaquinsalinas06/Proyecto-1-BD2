import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.table_manager import TableManager
from src.parser.ast import ColumnDef, DataType, IndexType, Value, CompCond, CompOp

def main():
    print("=== MINI DB MANAGER - PRUEBAS ===\n")

    db = TableManager()

    print("PRUEBA 1: Parser unitario")
    try:
        sqls = [
            "CREATE TABLE usuarios (id INT KEY INDEX BTREE, nombre VARCHAR[50], edad INT)",
            "SELECT * FROM usuarios WHERE edad > 18",
            "INSERT INTO usuarios VALUES (1, \"Juan\", 25)",
            "DELETE FROM usuarios WHERE edad < 18"
        ]

        for sql in sqls:
            statements = db.parser.parse(sql)
            for stmt in statements:
                print(f"{sql[:40]}... → {type(stmt).__name__}")
    except Exception as e:
        print(f"Error parser: {e}")

    print("\nPRUEBA 2: Creación de tablas")
    try:
        columns = [
            ColumnDef(name="id", data_type=DataType.INT, is_key=True, index_type=IndexType.HASH),
            ColumnDef(name="nombre", data_type=DataType.VARCHAR, size=50),
            ColumnDef(name="precio", data_type=DataType.FLOAT)
        ]
        db.create_table("productos", columns)
        print("Tabla 'productos' creada con índice HASH")

        columns_array = [
            ColumnDef(name="id", data_type=DataType.INT, is_key=True, index_type=IndexType.BTREE),
            ColumnDef(name="coordenadas", data_type=DataType.ARRAY, array_dimensions=2, element_type=DataType.FLOAT),
            ColumnDef(name="nombre", data_type=DataType.VARCHAR, size=30)
        ]
        db.create_table("ubicaciones", columns_array)
        print("Tabla 'ubicaciones' creada con arrays")

    except Exception as e:
        print(f"Error creación: {e}")

    print("\nPRUEBA 3: Inserción de datos")
    try:
        productos = [
            [Value(1, DataType.INT), Value("Laptop", DataType.VARCHAR), Value(899.99, DataType.FLOAT)],
            [Value(2, DataType.INT), Value("Mouse", DataType.VARCHAR), Value(25.50, DataType.FLOAT)],
            [Value(3, DataType.INT), Value("Teclado", DataType.VARCHAR), Value(45.00, DataType.FLOAT)],
            [Value(4, DataType.INT), Value("Monitor", DataType.VARCHAR), Value(299.99, DataType.FLOAT)]
        ]

        for i, producto in enumerate(productos, 1):
            db.insert("productos", producto)
            print(f"Producto {i} insertado")

        ubicaciones = [
            [Value(1, DataType.INT), Value([10.5, 20.3], DataType.ARRAY), Value("Centro", DataType.VARCHAR)],
            [Value(2, DataType.INT), Value([15.2, 25.8], DataType.ARRAY), Value("Norte", DataType.VARCHAR)]
        ]

        for ubicacion in ubicaciones:
            db.insert("ubicaciones", ubicacion)
        print("Ubicaciones con arrays insertadas")

    except Exception as e:
        print(f"Error inserción: {e}")

    print("\nPRUEBA 4: Consultas básicas")
    try:
        result = db.select("productos", ["*"])
        print(f"Todos los productos: {len(result)} encontrados")
        for r in result[:2]:
            print(f"   • {r['nombre']}: ${r['precio']}")

        result = db.select("productos", ["nombre", "precio"], limit=3)
        print(f"Consulta limitada: {len(result)} productos")

        result = db.select("productos", ["*"], order_by="precio", order_desc=True)
        print(f"Ordenado por precio (desc): {result[0]['nombre']} es el más caro")

    except Exception as e:
        print(f"Error consulta: {e}")

    print("\nPRUEBA 5: Consultas con filtros")
    try:
        condition = CompCond(
            column="precio",
            operator=CompOp.GREATER_THAN,
            value=Value(50.0, DataType.FLOAT)
        )
        result = db.select("productos", ["nombre", "precio"], where_condition=condition)
        print(f"Productos > $50: {len(result)} encontrados")

        condition_exact = CompCond(
            column="precio",
            operator=CompOp.EQUALS,
            value=Value(25.50, DataType.FLOAT)
        )
        result = db.select("productos", ["*"], where_condition=condition_exact)
        if result:
            print(f"Producto exacto: {result[0]['nombre']}")

    except Exception as e:
        print(f"Error filtros: {e}")

    print("\nPRUEBA 6: Eliminación de datos")
    try:
        before = len(db.select("productos", ["*"]))

        condition = CompCond(
            column="precio",
            operator=CompOp.LESS_THAN,
            value=Value(50.0, DataType.FLOAT)
        )
        deleted = db.delete("productos", where_condition=condition)
        print(f"Eliminados {deleted} productos < $50")

        after = len(db.select("productos", ["*"]))
        print(f"Productos restantes: {after} (antes: {before})")

    except Exception as e:
        print(f"Error eliminación: {e}")

    print("\nPRUEBA 7: Tipos de índices")
    try:
        indices_tipos = [
            ("seq_test", IndexType.SEQ),
            ("btree_test", IndexType.BTREE),
            ("hash_test", IndexType.HASH),
            ("isam_test", IndexType.ISAM)
        ]

        for tabla_name, index_type in indices_tipos:
            columns = [
                ColumnDef(name="id", data_type=DataType.INT, is_key=True, index_type=index_type),
                ColumnDef(name="data", data_type=DataType.VARCHAR, size=20)
            ]
            db.create_table(tabla_name, columns)

            db.insert(tabla_name, [Value(1, DataType.INT), Value("test", DataType.VARCHAR)])
            print(f"Tabla '{tabla_name}' con índice {index_type.value}")

    except Exception as e:
        print(f"Error índices: {e}")

    print("\nPRUEBA 8: Integración SQL completa")
    try:
        sql_create = "CREATE TABLE empleados (id INT KEY INDEX BTREE, nombre VARCHAR[30], salario FLOAT)"
        create_statements = db.parser.parse(sql_create)
        create_stmt = create_statements[0]

        db.create_table(create_stmt.table_name, create_stmt.columns)
        print("Tabla creada desde SQL parseado")

        sql_insert = "INSERT INTO empleados VALUES (1, \"Ana\", 3500.0)"
        insert_statements = db.parser.parse(sql_insert)
        insert_stmt = insert_statements[0]
        db.insert(insert_stmt.table_name, insert_stmt.values)
        print("Datos insertados desde SQL parseado")

        result = db.select("empleados", ["*"])
        print(f"Empleado: {result[0]['nombre']} - ${result[0]['salario']}")

    except Exception as e:
        print(f"Error integración: {e}")

    print(f"\nPRUEBAS COMPLETADAS")
    print(f"Tablas creadas: {len(db.tables)}")
    print(f"Tablas: {', '.join(db.tables.keys())}")

if __name__ == "__main__":
    main()