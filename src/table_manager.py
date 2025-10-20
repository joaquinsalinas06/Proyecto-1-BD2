import os
import csv
import json
from typing import List, Dict, Any, Optional
from .parser.ast import (
    ColumnDef, IndexType, Value, Condition, DataType,
    CompCond, BetweenCond, SpatialInCond,
    SpatialKNNCond, LogicCond, Statement,
    CreateTableStmt, CreateTableFileStmt, SelectStmt,
    InsertStmt, DeleteStmt, IndexSpec
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
        self.indices_directory = "indices"
        os.makedirs(self.indices_directory, exist_ok=True)
        self.metadata_file = os.path.join(self.indices_directory, "tables_metadata.json")

        self.parser = SQLParser()
        self._load_table_metadata()
        
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
                self.create_table_from_file(stmt.table_name, stmt.file_path, stmt.indexes)
                return {
                    "type": "create_table_from_file",
                    "message": f"Tabla '{stmt.table_name}' creada desde archivo",
                    "table_name": stmt.table_name
                }

            elif isinstance(stmt, InsertStmt):
                if self.insert(stmt.table_name, stmt.values):
                    print(f"Registro insertado en '{stmt.table_name}'")
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

        self._save_table_metadata()
    '''
    A partir de un archivo CSV, realizamos dos pasadas en streaming (sin cargar todo en memoria):
    1. Primera pasada: analizar tipos de datos y determinar tamaño óptimo para VARCHAR
    2. Segunda pasada: insertar registros en los índices
    '''
    def create_table_from_file(self, table_name: str, file_path: str, indexes: List['IndexSpec']):
        if table_name in self.tables:
            raise ValueError(f"La tabla '{table_name}' ya existe")

        # Extraer la columna primaria y crear diccionario de índices por columna
        primary_index_spec = None
        index_specs_by_column = {}

        for index_spec in indexes:
            index_specs_by_column[index_spec.column_name] = index_spec
            if index_spec.is_primary:
                primary_index_spec = index_spec

        if not primary_index_spec:
            raise ValueError("Debe especificar un índice primario")

        column_stats = {}

        # Primera pasada: Obtenemos estadísticas de las columnas
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            reader = csv.DictReader(file)
            headers = reader.fieldnames

            if not headers:
                raise ValueError(f"Archivo '{file_path}' vacío")

            for header in headers:
                column_stats[header] = {
                    'type': DataType.INT,
                    'max_length': 0
                }

            row_count = 0
            for row in reader:
                row_count += 1
                for header in headers:
                    value = row[header].strip()
                    stats = column_stats[header]

                    # Detectar formato de ubicación "(lat,lon)"
                    if value.startswith('(') and value.endswith(')') and ',' in value:
                        stats['type'] = DataType.ARRAY
                        continue

                    if value: 
                        is_int = value.isdigit() or (value.startswith('-') and len(value) > 1 and value[1:].isdigit())
                        is_float = value.lstrip('-').replace('.', '', 1).isdigit() and '.' in value and value.lstrip('-').replace('.', '', 1)

                        if is_int and stats['type'] == DataType.INT:
                            pass
                        elif is_float:
                            if stats['type'] == DataType.INT:
                                stats['type'] = DataType.FLOAT
                        else:
                            stats['type'] = DataType.VARCHAR
                            stats['max_length'] = max(stats['max_length'], len(value))
                    if stats['type'] == DataType.VARCHAR and value:
                        stats['max_length'] = max(stats['max_length'], len(value))

            if row_count == 0:
                raise ValueError(f"Archivo '{file_path}' sin datos")

        # Construimos el esquema con índices
        columns = []
        for header in headers:
            is_key = (header == primary_index_spec.column_name)
            index_spec = index_specs_by_column.get(header)
            col_index_type = index_spec.index_type if index_spec else None
            stats = column_stats[header]

            size = None
            element_type = None
            array_dimensions = None
            data_type = stats['type']

            if stats['type'] == DataType.VARCHAR:
                size = max(1, int(stats['max_length'] * 1.1))
            elif stats['type'] == DataType.ARRAY:
                element_type = DataType.FLOAT
                array_dimensions = 2

            column = ColumnDef(
                name=header,
                data_type=data_type,
                size=size,
                element_type=element_type,
                is_key=is_key,
                index_type=col_index_type,
                array_dimensions=array_dimensions
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
                    table_schema=table.columns,
                    expected_size=row_count
                )
                table.indexes[col.name] = index

        # Segunda pasada: insertar registros en índices
        all_records = []
        skipped_records = 0
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            reader = csv.DictReader(file)
            current_row = 0
            for row in reader:
                current_row += 1
                parsed_row = {}
                skip_record = False
                
                for col in table.columns:
                    value_str = row[col.name].strip() if row[col.name] else ""

                    if col.data_type == DataType.ARRAY:
                        if value_str.startswith('(') and value_str.endswith(')'):
                            coords_str = value_str[1:-1]
                            coords = [float(x.strip()) for x in coords_str.split(',')]
                            parsed_row[col.name] = tuple(coords)
                        else:
                            parsed_row[col.name] = value_str
                    elif col.data_type == DataType.INT:
                        try:
                            int_value = int(value_str) if value_str else 0
                            if int_value > 2147483647 or int_value < -2147483648:
                                skip_record = True
                                break
                            parsed_row[col.name] = int_value
                        except ValueError:
                            parsed_row[col.name] = value_str
                    elif col.data_type == DataType.BIGINT:
                        try:
                            parsed_row[col.name] = int(value_str) if value_str else 0
                        except ValueError:
                            parsed_row[col.name] = value_str
                    elif col.data_type == DataType.FLOAT:
                        try:
                            parsed_row[col.name] = float(value_str) if value_str else 0.0
                        except ValueError:
                            parsed_row[col.name] = value_str
                    else:
                        parsed_row[col.name] = value_str

                if not skip_record:
                    all_records.append(parsed_row)
                else:
                    skipped_records += 1

        
        # Cuando cargamos muchos registros, es mejor hacer bulk load en los indices primarios
        for _, index in table.indexes.items():
            if index is not None:
                # Si es que existe el metodo de bulk load lo usaremos, como en Sequential, ISAM o B+Tree
                if hasattr(index, 'bulk_load'):
                    index.bulk_load(all_records)
                else:
                    # Para los indices secundarios usaremos solo el add regular, por sus propiedades
                    for _, record in enumerate(all_records, 1):
                        index.add(record)

        self._save_table_metadata()

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

        select_all = "*" in columns # Verificar si se seleccionan todas las columnas
        results = []

        for record in filtered_dicts:
            formatted_record = {}

            for key, value in record.items():
                if not select_all and key not in columns: # Verificar si la columna está en la selección
                    continue

                if isinstance(value, (tuple, list)): # Formatear arrays como "(val1, val2)"
                    formatted_record[key] = f"({', '.join(str(v) for v in value)})"
                else:
                    formatted_record[key] = value

            results.append(formatted_record)

        return results

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
            pk_references = index.rangeSearch(point, radius)
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
            pk_references = index.knnSearch(point, k)
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

    '''
    Retorna metadatos de todas las tablas existentes: nombre, columnas, indices y cantidad de registros
    '''
    def get_all_tables_metadata(self) -> List[Dict[str, Any]]:
        tables_metadata = []

        for table_name, table in self.tables.items():
            columns_info = []
            indexed_columns = []

            # Extraemos informacion de cada columna
            for col in table.columns:
                col_info = {
                    "name": col.name,
                    "type": self._format_column_type(col),
                    "indexed": col.name in table.indexes,
                    "indexType": col.index_type.value if col.index_type else None,
                    "primaryKey": col.is_key
                }
                columns_info.append(col_info)

                if col.name in table.indexes:
                    indexed_columns.append(col.name)

            # Obtener cantidad de registros del indice primario
            row_count = 0
            if table.key_column and table.key_column in table.indexes:
                primary_index = table.indexes[table.key_column]
                row_count = len(primary_index.getAllRecords())

            tables_metadata.append({
                "name": table_name,
                "columns": columns_info,
                "row_count": row_count,
                "indexes": indexed_columns
            })

        return tables_metadata

    '''
    Retorna informacion detallada de una tabla especifica: esquema completo y muestra de los primeros registros
    '''
    def get_table_details(self, table_name: str, preview_limit: int = 100) -> Dict[str, Any]:
        if table_name not in self.tables:
            raise ValueError(f"La tabla '{table_name}' no existe")

        table = self.tables[table_name]

        # Construir informacion de cada columna
        columns_info = []
        for col in table.columns:
            columns_info.append({
                "name": col.name,
                "type": self._format_column_type(col),
                "indexed": col.name in table.indexes,
                "indexType": col.index_type.value if col.index_type else None,
                "primaryKey": col.is_key
            })

        # Obtener muestra de datos limitada
        preview_data = []
        if table.key_column and table.key_column in table.indexes:
            primary_index = table.indexes[table.key_column]
            all_records = primary_index.getAllRecords()
            preview_data = all_records[:preview_limit]

        return {
            "name": table_name,
            "description": f"Tabla '{table_name}' con {len(table.columns)} columnas",
            "columns": columns_info,
            "data": preview_data
        }

    '''
    Formatea el tipo de dato de una columna como string para mostrar al usuario
    Incluye el tamaño para VARCHAR y dimensiones para ARRAY
    '''
    def _format_column_type(self, col: ColumnDef) -> str:
        if col.data_type == DataType.VARCHAR and col.size:
            return f"VARCHAR[{col.size}]"
        elif col.data_type == DataType.ARRAY and col.array_dimensions:
            base_type = "FLOAT"
            return f"ARRAY[{col.array_dimensions}][{base_type}]"
        else:
            return col.data_type.value

    '''
    Guarda los metadatos de todas las tablas en un archivo JSON
    Permite reconstruir las tablas e indices al reiniciar el sistema
    Se usa JSON para facilidad de lectura y escritura con el frontend
    Y al contener solo metadatos, no es un archivo muy pesado
    '''
    def _save_table_metadata(self):
        metadata = {}

        # Por cada una de las tablas, guardamos su esquema y detalles de columnas
        for table_name, table in self.tables.items():
            columns_data = []
            for col in table.columns:
                col_data = {
                    "name": col.name,
                    "data_type": col.data_type.value,
                    "size": col.size,
                    "element_type": col.element_type.value if col.element_type else None,
                    "is_key": col.is_key,
                    "index_type": col.index_type.value if col.index_type else None,
                    "array_dimensions": col.array_dimensions
                }
                columns_data.append(col_data)

            metadata[table_name] = {
                "name": table_name,
                "columns": columns_data
            }

        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    '''
    Carga los metadatos desde el archivo JSON y reconstruye todas las tablas con sus indices
    Se ejecuta al iniciar el TableManager para recuperar el estado previo del sistema
    '''
    def _load_table_metadata(self):
        if not os.path.exists(self.metadata_file):
            return

        with open(self.metadata_file, 'r') as f:
            metadata = json.load(f)

        for table_name, table_data in metadata.items():
            # Reconstruir columnas desde metadatos
            columns = []
            for col_data in table_data["columns"]:
                col = ColumnDef(
                    name=col_data["name"],
                    data_type=DataType(col_data["data_type"]),
                    size=col_data.get("size"),
                    element_type=DataType(col_data["element_type"]) if col_data.get("element_type") else None,
                    is_key=col_data.get("is_key", False),
                    index_type=IndexType(col_data["index_type"]) if col_data.get("index_type") else None,
                    array_dimensions=col_data.get("array_dimensions")
                )
                columns.append(col)

            # Crear tabla y reconstruir sus indices desde archivos existentes
            table = Table(table_name, columns)
            primary_key_col = table.key_column

            for col in columns:
                if col.index_type:
                    filename = f"indices/{table_name}_{col.name}.dat"
                    index = create_index(
                        index_type=col.index_type,
                        column_name=col.name,
                        filename=filename,
                        is_primary=col.is_key,
                        primary_key_column=primary_key_col if not col.is_key else None,
                        table_schema=table.columns
                    )
                    table.indexes[col.name] = index

            self.tables[table_name] = table
    
    def get_io_stats(self, table_name: str) -> Dict[str, int]:
        if table_name not in self.tables:
            return {}
        
        table = self.tables[table_name]
        primary_index = table.indexes.get(table.key_column)
        
        if primary_index and hasattr(primary_index, 'get_io_stats'):
            return primary_index.get_io_stats()
        
        return {}
    
    def reset_io_stats(self, table_name: str):
        if table_name not in self.tables:
            return
        
        table = self.tables[table_name]
        primary_index = table.indexes.get(table.key_column)
        
        if primary_index and hasattr(primary_index, 'reset_io_stats'):
            primary_index.reset_io_stats()