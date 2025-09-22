import os
import csv
from typing import List, Dict, Any, Optional
from .parser.ast import (
    ColumnDef, IndexType, Value, Condition, DataType,
    CompCond, BetweenCond, SpatialInCond,
    SpatialKNNCond, LogicCond
)
from .parser.sql_parser import SQLParser
from .records import DynamicRecord
from .records.indices import create_index


class Table:
    def __init__(self, name: str, columns: List[ColumnDef]):
        self.name = name
        self.columns = columns
        self.column_names = [col.name for col in columns]
        self.schema = columns 

        self.records = []
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
    
    def create_record_from_dict(self, data: Dict[str, Any]):
        return DynamicRecord(self.schema, **data)


class TableManager:
    def __init__(self):
        self.tables: Dict[str, Table] = {}
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_directory = os.path.join(project_root, "data")
        os.makedirs(self.data_directory, exist_ok=True)

        self.parser = SQLParser()
    
    def create_table(self, table_name: str, columns: List[ColumnDef]):
        if table_name in self.tables:
            raise ValueError(f"La tabla '{table_name}' ya existe")
        
        table = Table(table_name, columns)
        self.tables[table_name] = table
        
        for col in table.columns:
            if col.index_type:
                index = create_index(col.index_type, col.name)
                table.indexes[col.name] = index
            elif col.is_key and col.index_type is None:
                col.index_type = IndexType.BTREE
                index = create_index(col.index_type, col.name)
                table.indexes[col.name] = index

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
        
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                record = table.create_record_from_dict(row)
                table.records.append(record)
                
        for col in table.columns:
            if col.index_type:
                index = create_index(col.index_type, col.name)
                table.indexes[col.name] = index

    
    def insert(self, table_name: str, values: List[Value]):
        if table_name not in self.tables:
            raise ValueError(f"La tabla '{table_name}' no existe")
        table = self.tables[table_name]
        record = table.create_record_from_values(values)

        # Agregar a la tabla
        table.records.append(record)

        # Agregar a los índices
        record_dict = {}
        for col in table.columns:
            record_dict[col.name] = getattr(record, col.name)

        for col_name, index in table.indexes.items():
            if index is not None:  # Solo si el índice fue creado exitosamente
                try:
                    index.add(record_dict)
                except Exception as e:
                    print(f"  [WARN] Error agregando a índice {col_name}: {e}")

        print(f"[OK] Registro insertado: {record}")
    
    def select(self, table_name: str, columns: List[str],
              where_condition: Optional[Condition] = None,
              order_by: Optional[str] = None,
              order_desc: bool = False,
              limit: Optional[int] = None) -> List[Dict[str, Any]]:
        
        if table_name not in self.tables:
            raise ValueError(f"La tabla '{table_name}' no existe")
        table = self.tables[table_name]

        if where_condition:
            filtered_records = self._filter_records_with_indexes(table, where_condition)
        else:
            filtered_records = table.records.copy()

        if order_by:
            try:
                filtered_records.sort(
                    key=lambda r: getattr(r, order_by),
                    reverse=order_desc
                )
            except AttributeError:
                raise ValueError(f"Columna '{order_by}' no encontrada")

        if limit:
            filtered_records = filtered_records[:limit]

        result = []
        for record in filtered_records:
            if columns == ["*"]:
                record_dict = {}
                for col in table.columns:
                    record_dict[col.name] = getattr(record, col.name)
            else:
                record_dict = {}
                for col_name in columns:
                    if hasattr(record, col_name):
                        record_dict[col_name] = getattr(record, col_name)
            result.append(record_dict)

        return result
    
    def delete(self, table_name: str, where_condition: Optional[Condition] = None) -> int:
        if table_name not in self.tables:
            raise ValueError(f"La tabla '{table_name}' no existe")
        table = self.tables[table_name]

        if where_condition is None:
            # Clear all records and indexes
            deleted_count = len(table.records)
            table.records.clear()

            # Clear all indexes
            for col_name, index in table.indexes.items():
                if index is not None:
                    try:
                        # seq_TODO: SequentialFileIndex needs clear_all() method
                        # btree_TODO: BTreeIndex needs clear_all() method
                        # hash_TODO: ExtendibleHashIndex needs clear_all() method
                        # isam_TODO: ISAMIndex needs clear_all() method
                        # rtree_TODO: RTreeIndex needs clear_all() method
                        pass  # Placeholder - each index should implement clear_all()
                    except Exception as e:
                        print(f"  [WARN]  Error clearing index {col_name}: {e}")

            return deleted_count

        # DELETE with WHERE condition
        records_to_delete = self._filter_records_with_indexes(table, where_condition)
        deleted_count = 0

        for record in records_to_delete:
            # Remove from table
            if record in table.records:
                table.records.remove(record)
                deleted_count += 1

                # Remove from indexes
                record_dict = {}
                for col in table.columns:
                    record_dict[col.name] = getattr(record, col.name)

                for col_name, index in table.indexes.items():
                    if index is not None:
                        try:
                            key = record_dict[col_name]
                            index.remove(key)
                        except Exception as e:
                            print(f"  [WARN]  Error removing from index {col_name}: {e}")

        return deleted_count

    def _filter_records_with_indexes(self, table: Table, condition: Condition) -> List:
        if isinstance(condition, CompCond):
            # Búsqueda por comparación: =, !=, <, <=, >, >=
            column_name = condition.column
            operator = condition.operator.value
            value = condition.value.value

            index = table.indexes.get(column_name)
            if index is None:
                print(f"  [WARN]  Sin índice para '{column_name}', búsqueda lineal")
                return table.records.copy()  # Placeholder: devolver todos

            try:
                if operator == "=":
                    # Búsqueda exacta
                    results = index.search(value)
                    # seq_TODO: SequentialFileIndex.search() implementar
                    # btree_TODO: BTreeIndex.search() implementar
                    # hash_TODO: ExtendibleHashIndex.search() implementar
                    # isam_TODO: ISAMIndex.search() implementar

                    # Por ahora devolver registros que coincidan (placeholder)
                    return [r for r in table.records if getattr(r, column_name) == value]

                elif operator in ["<", "<=", ">", ">="]:
                    # Búsqueda por rango
                    results = index.rangeSearch(None, None)  # Placeholder
                    # seq_TODO: SequentialFileIndex.rangeSearch() implementar
                    # btree_TODO: BTreeIndex.rangeSearch() implementar
                    # isam_TODO: ISAMIndex.rangeSearch() implementar
                    # hash_TODO: No soporta búsqueda por rango

                    # Por ahora comparación directa (placeholder)
                    if operator == "<":
                        return [r for r in table.records if getattr(r, column_name) < value]
                    elif operator == "<=":
                        return [r for r in table.records if getattr(r, column_name) <= value]
                    elif operator == ">":
                        return [r for r in table.records if getattr(r, column_name) > value]
                    elif operator == ">=":
                        return [r for r in table.records if getattr(r, column_name) >= value]

                elif operator == "!=":
                    return [r for r in table.records if getattr(r, column_name) != value]

            except Exception as e:
                print(f"  [WARN]  Error en índice '{column_name}': {e}")
                return table.records.copy()

        elif isinstance(condition, BetweenCond):
            # Búsqueda BETWEEN
            column_name = condition.column
            start_value = condition.start_value.value
            end_value = condition.end_value.value

            index = table.indexes.get(column_name)
            if index is None:
                print(f"  [WARN]  Sin índice para '{column_name}', búsqueda lineal")
                return [r for r in table.records if start_value <= getattr(r, column_name) <= end_value]

            try:
                results = index.rangeSearch(start_value, end_value)
                # seq_TODO: SequentialFileIndex.rangeSearch() implementar
                # btree_TODO: BTreeIndex.rangeSearch() implementar
                # isam_TODO: ISAMIndex.rangeSearch() implementar

                # Placeholder: comparación directa
                return [r for r in table.records if start_value <= getattr(r, column_name) <= end_value]

            except Exception as e:
                print(f"  [WARN]  Error en índice '{column_name}': {e}")
                return [r for r in table.records if start_value <= getattr(r, column_name) <= end_value]

        elif isinstance(condition, SpatialInCond):
            # Búsqueda espacial IN (punto, radio)
            column_name = condition.column
            point = condition.point
            radius = condition.radius

            index = table.indexes.get(column_name)
            if index is None:
                print(f"  [WARN]  Sin índice espacial para '{column_name}'")
                return []  # Placeholder

            try:
                results = index.rangeSearch((point.x, point.y), radius)
                # rtree_TODO: RTreeIndex.rangeSearch() espacial implementar
                return []  # Placeholder

            except Exception as e:
                print(f"  [WARN]  Error en índice espacial '{column_name}': {e}")
                return []

        elif isinstance(condition, SpatialKNNCond):
            # Búsqueda KNN
            column_name = condition.column
            point = condition.point
            k = condition.k

            index = table.indexes.get(column_name)
            if index is None:
                print(f"  [WARN]  Sin índice espacial para '{column_name}'")
                return []  # Placeholder

            try:
                results = index.knnSearch((point.x, point.y), k)
                # rtree_TODO: RTreeIndex.knnSearch() implementar
                return []  # Placeholder

            except Exception as e:
                print(f"  [WARN]  Error en KNN '{column_name}': {e}")
                return []

        elif isinstance(condition, LogicCond):
            # AND/OR
            left_results = self._filter_records_with_indexes(table, condition.left)
            right_results = self._filter_records_with_indexes(table, condition.right)

            if condition.operator.value == "AND":
                return [r for r in left_results if r in right_results]
            elif condition.operator.value == "OR":
                combined = left_results.copy()
                for r in right_results:
                    if r not in combined:
                        combined.append(r)
                return combined

        # Fallback: devolver todos los registros
        print(f"  [WARN]  Tipo de condición no soportado: {type(condition)}")
        return table.records.copy()


