import os
import csv
from typing import List, Dict, Any, Optional
from .parser.ast import (
    ColumnDef, IndexType, Value, Condition, DataType,
    CompCond, BetweenCond, SpatialInCond,
    SpatialKNNCond, LogicCond, Statement,
    CreateTableStmt, CreateTableFileStmt, SelectStmt,
    InsertStmt, DeleteStmt
)
from .parser.sql_parser import SQLParser
from src.records import DynamicRecord
from src.records.indices import create_index

'''
La clase Table representa una tabla en la base de datos, con su esquema y sus índices, de tal forma
que siempre tenemos conocimiento a los datos de dicha tabla, como nombre, columnas, tipos de datos, etc.

create_record_from_values: Dada una lista de valores, crea un DynamicRecord con los valores asignados a las columnas
get_primary_index: Retorna el índice primario de la tabla, si no existe lanza un error
'''
class Table:
    def __init__(self, name: str, columns: List[ColumnDef]):
        self.name = name
        self.columns = columns
        self.column_names = [col.name for col in columns]
        self.schema = columns 

        self.indexes = {}

        self.key_column = None
        for col in columns:
            if col.is_key:
                self.key_column = col.name
                break

    def create_record_from_values(self, values: List[Value]):
        if len(values) != len(self.columns):
            raise ValueError(f"Se esperaban {len(self.columns)} valores, se recibieron {len(values)}")
        
        kwargs = {}
        for col, value in zip(self.columns, values):
            val = value.value
            if hasattr(val, 'x') and hasattr(val, 'y'):
                val = (val.x, val.y)
            kwargs[col.name] = val

        return DynamicRecord(self.schema, **kwargs)
    
    def get_primary_index(self):
        if not self.key_column or self.key_column not in self.indexes:
            raise ValueError(f"No hay índice primario para la tabla '{self.name}'")
        return self.indexes[self.key_column]


class TableManager:
    def __init__(self):
        self.tables: Dict[str, Table] = {}
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_directory = os.path.join(project_root, "data")
        os.makedirs(self.data_directory, exist_ok=True)

        self.parser = SQLParser()
        
    #Se manda directamente el query a la funcion sql, que se encarga de parsearlo y ejecutar cada stmt
    def sql(self, query: str) -> List[Dict[str, Any]]:
        statements = self.parser.parse(query)
        results = []

        for stmt in statements:
            result = self._execute_statement(stmt)
            results.append(result)

        return results

    # Para cada uno de los stmts, se verifica que tipo es y se llama a la funcion/operacion correcta
    def _execute_statement(self, stmt: Statement) -> Dict[str, Any]: 
        try:
            if isinstance(stmt, CreateTableStmt):
                self.create_table(stmt.table_name, stmt.columns)
                return {
                    "type": "create_table",
                    "message": f"Tabla '{stmt.table_name}' creada exitosamente",
                    "table_name": stmt.table_name
                }

            elif isinstance(stmt, CreateTableFileStmt):
                self.create_table_from_file(stmt.table_name, stmt.file_path,
                                          stmt.index_type, stmt.key_column)
                return {
                    "type": "create_table_from_file",
                    "message": f"Tabla '{stmt.table_name}' creada desde archivo",
                    "table_name": stmt.table_name
                }

            elif isinstance(stmt, InsertStmt):
                self.insert(stmt.table_name, stmt.values)
                return {
                    "type": "insert",
                    "message": f"Registro insertado en '{stmt.table_name}'",
                    "table_name": stmt.table_name
                }

            elif isinstance(stmt, SelectStmt):
                data = self.select(
                    stmt.table_name,
                    stmt.columns,
                    stmt.where_condition,
                    stmt.order_by,
                    stmt.order_desc,
                    stmt.limit
                )
                return {
                    "type": "select",
                    "data": data,
                    "table_name": stmt.table_name,
                    "rows_count": len(data)
                }

            elif isinstance(stmt, DeleteStmt):
                deleted_count = self.delete(stmt.table_name, stmt.where_condition)
                return {
                    "type": "delete",
                    "message": f"{deleted_count} registros eliminados de '{stmt.table_name}'",
                    "table_name": stmt.table_name,
                    "deleted_count": deleted_count
                }

            else:
                return {
                    "error": f"Tipo de sentencia no soportado:",
                    "type": "execution_error"
                }

        except NotImplementedError:
            raise

        except Exception as e:
            return {
                "error": str(e),
                "type": "Error ejecutando sentencia",
                "statement_type": type(stmt).__name__
            }
        
    '''
    Por cada una de las columnas que tenemos, verificamos si tiene un indice asociado
    aqui diferenciamos si es un indice primario o secundario
    en caso identificamos una columna que es llave primaria pero no tiene indice, le asignamos un BTree por defecto
    '''
    def create_table(self, table_name: str, columns: List[ColumnDef]):
        if table_name in self.tables:
            raise ValueError(f"La tabla '{table_name}' ya existe")
        
        table = Table(table_name, columns)
        self.tables[table_name] = table
        
        for col in table.columns:
            if col.index_type:
                index = create_index(
                    col.index_type,
                    col.name,
                    filename=f"indices/{table.name}_{col.name}.dat",
                    is_primary=col.is_key,
                    primary_key_column=table.key_column if not col.is_key else None,
                    table_schema=table.columns
                )
                table.indexes[col.name] = index
            elif col.is_key and col.index_type is None:
                col.index_type = IndexType.BTREE
                index = create_index(
                    col.index_type,
                    col.name,
                    filename=f"indices/{table.name}_{col.name}.dat",
                    is_primary=True,
                    primary_key_column=None,
                    table_schema=table.columns
                )
                table.indexes[col.name] = index

    '''
    A partir de un archivo CSV, obtenemos la caberera y la primera fila para inferir los tipos de datos
    Creamos las columnas y la tabla, y luego insertamos cada uno de los registros en la tabla
    Ademas, por cada columna que tenga un indice, insertamos el registro en el indice
    '''
    def create_table_from_file(self, table_name: str, file_path: str, 
                             index_type: IndexType, key_column: str):
        if table_name in self.tables:
            raise ValueError(f"La tabla '{table_name}' ya existe")
        
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            headers = reader.fieldnames
            
            if not headers:
                raise ValueError(f"Archivo '{file_path}' vacío")
            
            first_row = next(reader, None)
            if not first_row:
                raise ValueError(f"Archivo '{file_path}' sin datos")
        
        columns = []
        for header in headers:
            is_key = (header == key_column)
            col_index_type = index_type if is_key else None
        
            data_type = DataType.VARCHAR
            size = 50
            
            if first_row[header].isdigit():
                data_type = DataType.INT
                size = None
            elif '.' in first_row[header] and first_row[header].replace('.', '').replace('-', '').isdigit():
                data_type = DataType.FLOAT
                size = None
            
            column = ColumnDef(
                name=header,
                data_type=data_type,
                size=size,
                is_key=is_key,
                index_type=col_index_type
            )
            columns.append(column)
        
    
        table = Table(table_name, columns)
        self.tables[table_name] = table

        for col in table.columns:
            if col.index_type:
                index = create_index(
                    col.index_type,
                    col.name,
                    filename=f"indices/{table.name}_{col.name}.dat",
                    is_primary=col.is_key,
                    primary_key_column=table.key_column if not col.is_key else None,
                    table_schema=table.columns
                )
                table.indexes[col.name] = index
                
            for row in reader:
                for _, index in table.indexes.items():
                    if index is not None:
                            index.add(row)

    '''
    Insertamos un registro en la tabla, verificando que la tabla exista
    Por cada columna que tenga un indice, insertamos el registro en el indice
    '''
    def insert(self, table_name: str, values: List[Value]):
        if table_name not in self.tables:
            raise ValueError(f"La tabla '{table_name}' no existe")
        table = self.tables[table_name]
        record_dict = {}
        for col, value in zip(table.columns, values):
            val = value.value
            if hasattr(val, 'x') and hasattr(val, 'y'):
                val = (val.x, val.y)
            record_dict[col.name] = val

        for _, index in table.indexes.items():
            if index is not None:
                index.add(record_dict)


    '''
    Al realizar una busqueda, verificaremos si es que existe algun tipo de condicion para filtrar los registros
    luego si es que existe algun orden en especifico y finalmente si tenemos un limite de registros a retornar
    Si se seleccionan todas las columnas, retornamos todos los registros, sino solo las columnas especificadas
    '''
    def select(self, table_name: str, columns: List[str],
              where_condition: Optional[Condition] = None,
              order_by: Optional[str] = None,
              order_desc: bool = False,
              limit: Optional[int] = None) -> List[Dict[str, Any]]:
        
        if table_name not in self.tables:
            raise ValueError(f"La tabla '{table_name}' no existe")
        table = self.tables[table_name]

        if where_condition:
            filtered_dicts = self._execute_condition(table, where_condition)
        else:
            index = table.get_primary_index()
            filtered_dicts = index.getAllRecords()

        if order_by:
            filtered_dicts.sort(key=lambda d: d.get(order_by), reverse=order_desc)

        if limit:
            filtered_dicts = filtered_dicts[:limit]

        if "*" in columns:
            return filtered_dicts

        res = []
        for record in filtered_dicts:
            selected = {col: record.get(col) for col in columns if col in record}
            res.append(selected)

        return res

    '''
    Si no existe un filtro de borrado, se eliminan todos los registros de la tabla
    Si existe un filtro, se obtienen los registros a eliminar y por cada uno de ellos
    se eliminan de los indices asociados a la tabla, en cada uno d elos indices y se devuelve
    la cantidad de registros eliminados
    '''
    def delete(self, table_name: str, where_condition: Optional[Condition] = None) -> int:
        if table_name not in self.tables:
            raise ValueError(f"La tabla '{table_name}' no existe")
        table = self.tables[table_name]

        if where_condition is None:
            for col_name, index in table.indexes.items():
                if index is not None:
                    deleted_count = index.clear_all();

            return deleted_count


        records_to_delete = self._execute_condition(table, where_condition)
        deleted_count = 0

        for record_dict in records_to_delete:
            deleted_count += 1
            for col_name, index in table.indexes.items():
                if index is not None:
                    key = record_dict.get(col_name)
                    # Para índices secundarios, pasar la primary key para eliminar solo ese registro específico
                    if not index.is_primary and table.key_column:
                        pk_value = record_dict.get(table.key_column)
                        index.remove(key, primary_key=pk_value)
                    else:
                        index.remove(key)
        return deleted_count

    '''
    Este es el core de la obtencion de registros con condiciones
    Dependiendo del tipo de condicion, se realiza la busqueda correspondiente
    '''
    def _execute_condition(self, table: Table, condition: Condition) -> List:
        if isinstance(condition, CompCond):
            return self._comparison_condition(table, condition)

        elif isinstance(condition, BetweenCond):
            return self._between_condition(table, condition)

        elif isinstance(condition, SpatialInCond):
            return self._spatial_in_condition(table, condition)

        elif isinstance(condition, SpatialKNNCond):
            return self._spatial_knn_condition(table, condition)

        elif isinstance(condition, LogicCond):
            return self._logic_condition(table, condition)

        return table.get_primary_index().getAllRecords()

    '''
    Aqui se aprovechan principalmente los indices para realizar las busquedas
    Si no existe un indice para la columna, se realiza un escaneo completo de la tabla y se filtran los datos
    En el caso de los indices secundarios, se obtiene una referencia (la llave primaria) y se vuelve a realizar
    una busqueda en el indice primario para obtener el registro completo
    '''
    def _comparison_condition(self, table: Table, condition: CompCond) -> List:
        column_name = condition.column
        operator = condition.operator.value
        search_value = condition.value.value

        index = table.indexes.get(column_name)

        if index is None:
            all_records = table.get_primary_index().getAllRecords()
            matching_records = []
            for record in all_records:
                record_value = record.get(column_name)
                match = False

                if operator == "=" and record_value == search_value:
                    match = True
                elif operator == "!=" and record_value != search_value:
                    match = True
                elif operator == "<" and record_value < search_value:
                    match = True
                elif operator == "<=" and record_value <= search_value:
                    match = True
                elif operator == ">" and record_value > search_value:
                    match = True
                elif operator == ">=" and record_value >= search_value:
                    match = True

                if match:
                    matching_records.append(record)

            return matching_records

        try:
            if operator == "=":
                index_results = index.search(search_value)
            elif operator == "<":
                index_results = index.rangeSearch(None, search_value, begin_inclusive=True, end_inclusive=False)
            elif operator == "<=":
                index_results = index.rangeSearch(None, search_value, begin_inclusive=True, end_inclusive=True)
            elif operator == ">":
                index_results = index.rangeSearch(search_value, None, begin_inclusive=False, end_inclusive=True)
            elif operator == ">=":
                index_results = index.rangeSearch(search_value, None, begin_inclusive=True, end_inclusive=True)
            elif operator == "!=":
                all_records = index.getAllRecords()
                filtered_records = []
                for record in all_records:
                    if record.get(index.column_name) != search_value:
                        filtered_records.append(record)
                return filtered_records
            else:
                raise ValueError(f"Operador no soportado {operator}")

            if index.is_primary:
                return index_results
            
            if not table.key_column:
                return []

            primary_key_values = []
            for reference in index_results:
                if table.key_column in reference:
                    pk_value = reference.get(table.key_column)
                    primary_key_values.append(pk_value)

            primary_index = table.indexes.get(table.key_column)
            if primary_index:
                full_records = []
                for pk_value in primary_key_values:
                    records = primary_index.search(pk_value)
                    full_records.extend(records)
                return full_records

            all_records = table.get_primary_index().getAllRecords()
            matching_records = []
            for record in all_records:
                if record.get(table.key_column) in primary_key_values:
                    matching_records.append(record)
            return matching_records

        except NotImplementedError:
            raise

        except Exception:
            all_records = table.get_primary_index().getAllRecords()
            matching_records = []
            for record in all_records:
                record_value = record.get(column_name)
                match = False

                if operator == "=" and record_value == search_value:
                    match = True
                elif operator == "!=" and record_value != search_value:
                    match = True
                elif operator == "<" and record_value < search_value:
                    match = True
                elif operator == "<=" and record_value <= search_value:
                    match = True
                elif operator == ">" and record_value > search_value:
                    match = True
                elif operator == ">=" and record_value >= search_value:
                    match = True

                if match:
                    matching_records.append(record)

            return matching_records

    '''
    Aqui aprovechamos principalmete el range search de los indices (Hash no soporta range search y RTree usa un tipo de rango espacial)
    Nuevamente si no existe indice se toman todos los registros y si es secundario se obtienen las referencias para buscar en el primario
    '''
    def _between_condition(self, table: Table, condition: BetweenCond) -> List:
        column_name = condition.column
        start_value = condition.start_value.value
        end_value = condition.end_value.value

        index = table.indexes.get(column_name)

        if index is None:
            all_records = table.get_primary_index().getAllRecords()
            matching_records = []
            for record in all_records:
                record_value = record.get(column_name)
                if start_value <= record_value <= end_value:
                    matching_records.append(record)
            return matching_records

        try:
            index_results = index.rangeSearch(start_value, end_value, begin_inclusive=True, end_inclusive=True)

            if index.is_primary:
                return index_results

            if not table.key_column:
                return []

            primary_key_values = []
            for reference in index_results:
                if table.key_column in reference:
                    pk_value = reference.get(table.key_column)
                    primary_key_values.append(pk_value)

            primary_index = table.indexes.get(table.key_column)
            if primary_index:
                full_records = []
                for pk_value in primary_key_values:
                    records = primary_index.search(pk_value)
                    full_records.extend(records)
                return full_records

            all_records = table.get_primary_index().getAllRecords()
            matching_records = []
            for record in all_records:
                if record.get(table.key_column) in primary_key_values:
                    matching_records.append(record)
            return matching_records

        except NotImplementedError:
            raise

        except Exception:

            all_records = table.get_primary_index().getAllRecords()
            matching_records = []
            for record in all_records:
                record_value = record.get(column_name)
                if start_value <= record_value <= end_value:
                    matching_records.append(record)
            return matching_records

    '''
    Esta busqueda es exclusiva de los indices espaciales (RTree), en este caso se le brinda un punto y un radio
    y mediante el metodo rangeSearch del indice, se obtienen las referencias a los registros que cumplen con la condicion
    Luego se busca en el indice primario para obtener los registros completos
    '''
    def _spatial_in_condition(self, table: Table, condition: SpatialInCond) -> List:
        column_name = condition.column
        point = condition.point
        radius = condition.radius

        index = table.indexes.get(column_name)
        if index is None:
            return []

        try:
            pk_references = index.rangeSearch((point.x, point.y), radius)
            primary_index = table.get_primary_index()

            full_records = []
            for pk_ref in pk_references:
                pk_value = pk_ref[table.key_column]
                records = primary_index.search(pk_value)
                full_records.extend(records)

            return full_records

        except Exception:
            return []

    '''
    Esta busqueda nuevamente es solo para los RTree, donde se le brinda un punto y un k, que es la cantidad de registros 
    más cercanos a ese punto que se desean obtener
    Nuevamente se obtienen las referencias y se busca en el indice primario para obtener los registros completos
    '''
    def _spatial_knn_condition(self, table: Table, condition: SpatialKNNCond) -> List:
        column_name = condition.column
        point = condition.point
        k = condition.k

        index = table.indexes.get(column_name)
        if index is None:
            return []

        try:
            pk_references = index.knnSearch((point.x, point.y), k)
            primary_index = table.get_primary_index()

            full_records = []
            for pk_ref in pk_references:
                pk_value = pk_ref[table.key_column]
                records = primary_index.search(pk_value)
                full_records.extend(records)

            return full_records

        except Exception:
            return []

    '''
    Esta funcion se encarga de manejar las condiciones logicas AND y OR, de tal forma que podamos encadenar multiples
    condiciones en una sola consulta
    '''
    def _logic_condition(self, table: Table, condition: LogicCond) -> List:
        left_results = self._execute_condition(table, condition.left)
        right_results = self._execute_condition(table, condition.right)

        if condition.operator.value == "AND":
            intersection_results = []
            for record in left_results:
                if record in right_results:
                    intersection_results.append(record)
            return intersection_results

        elif condition.operator.value == "OR":
            union_results = left_results.copy()
            for record in right_results:
                if record not in union_results:
                    union_results.append(record)
            return union_results

        return []