"""
ESTRUCTURA ISAM CON CRECIMIENTO DINÁMICO DE 2 A 3 NIVELES:
---------------------------------------------------------------
- Construcción inicial: SIEMPRE 2 niveles (hojas + índice primario)
- Expansión dinámica: Crece a 3 niveles si nodos intermedios > BLOCK_FACTOR
- Overflow: Páginas encadenadas para nuevas inserciones
"""

from typing import List, Dict, Any, Optional, Union
import os
import struct
import pickle
from .base_index import BaseIndex
from ..record import DynamicRecord
from ...parser.ast import ColumnDef

BLOCK_FACTOR = 5  

class Page:
    """Página de datos con encadenamiento para overflow"""
    HEADER_FORMAT = 'iiq'  
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    def __init__(self, records=None, next_page=-1, overflow_pointer=-1, record_size=None):
        self.records = records or []
        self.next_page = next_page
        self.overflow_pointer = overflow_pointer
        self.record_size = record_size
    
    @property
    def SIZE_OF_PAGE(self):
        return self.HEADER_SIZE + BLOCK_FACTOR * self.record_size

    def pack(self) -> bytes:
        header_data = struct.pack(self.HEADER_FORMAT, len(self.records), 
                                  self.next_page, self.overflow_pointer)
        record_data = b''
        
        for record in self.records:
            record_data += record.pack()
        
        empty_slots = BLOCK_FACTOR - len(self.records)
        record_data += b'\x00' * (self.record_size * empty_slots)
        
        return header_data + record_data

    @staticmethod
    def unpack(data: bytes, table_schema: List[ColumnDef], record_size: int):
        size, next_page, overflow_pointer = struct.unpack(
            Page.HEADER_FORMAT, data[:Page.HEADER_SIZE]
        )
        offset = Page.HEADER_SIZE
        records = []
        
        for i in range(size):
            record_data = data[offset: offset + record_size]
            if record_data != b'\x00' * record_size:
                try:
                    record = DynamicRecord.unpack(table_schema, record_data)
                    if not record.deleted:
                        records.append(record)
                except:
                    pass
            offset += record_size
            
        return Page(records, next_page, overflow_pointer, record_size)


class ISAMIntermediateNode:
    """Nodo intermedio del árbol de índice"""
    def __init__(self, values=None, pointers=None, level=0):
        self.is_leaf = False
        self.values = values or []
        self.pointers = pointers or []
        self.level = level
        
    def pack(self) -> bytes:
        data = {
            'is_leaf': False,
            'values': self.values,
            'pointers': self.pointers,
            'level': self.level
        }
        return pickle.dumps(data)
    
    @staticmethod
    def unpack(data: bytes):
        try:
            obj = pickle.loads(data)
            return ISAMIntermediateNode(
                obj['values'], 
                obj['pointers'], 
                obj.get('level', 0)
            )
        except:
            return ISAMIntermediateNode()
    
    def find_child_index_binary(self, key: Any) -> int:
        """Búsqueda binaria del hijo correcto"""
        left, right = 0, len(self.values) - 1
        result = len(self.values)
        
        while left <= right:
            mid = (left + right) // 2
            if key < self.values[mid]:
                result = mid
                right = mid - 1
            else:
                left = mid + 1
        
        return result


class ISAMLeafNode:
    """Nodo hoja que apunta a páginas de datos"""
    def __init__(self, key_value=None, data_page_pointer=-1, next_pointer=-1):
        self.is_leaf = True
        self.key_value = key_value
        self.data_page_pointer = data_page_pointer
        self.next_pointer = next_pointer
        
    def pack(self) -> bytes:
        data = {
            'is_leaf': True,
            'key_value': self.key_value,
            'data_page_pointer': self.data_page_pointer,
            'next_pointer': self.next_pointer
        }
        return pickle.dumps(data)
    
    @staticmethod
    def unpack(data: bytes):
        try:
            obj = pickle.loads(data)
            return ISAMLeafNode(
                obj['key_value'],
                obj['data_page_pointer'],
                obj['next_pointer']
            )
        except:
            return ISAMLeafNode()


class ISAMMetadata:
    """Metadatos persistentes del índice"""
    def __init__(self):
        self.root_pointer = -1
        self.num_levels = 0
        self.num_records = 0
        self.num_pages = 0
        self.num_leaf_nodes = 0
        self.is_built = False
        
    def pack(self) -> bytes:
        return pickle.dumps(self.__dict__)
    
    @staticmethod
    def unpack(data: bytes):
        metadata = ISAMMetadata()
        try:
            metadata.__dict__ = pickle.loads(data)
        except:
            pass
        return metadata


class ISAMIndex(BaseIndex):
    """
    ISAM con construcción inicial de 2 niveles y expansión dinámica a 3 niveles.
    """
    
    def __init__(self, column_name: str, table_schema: List[ColumnDef], 
                 filename: str = None, block_factor: int =BLOCK_FACTOR ,
                 is_primary: bool = False, primary_key_column: str = None):
        super().__init__(column_name, filename, is_primary, primary_key_column)
        self.table_schema = table_schema
        self.block_factor = block_factor
        self.column_name = column_name
        
        self.record_format = DynamicRecord._build_format(table_schema)
        self.record_size = struct.calcsize(self.record_format)
        
        base_name = filename.replace('.dat', '') if filename else column_name
        self.data_file = f"{base_name}_data.dat"
        self.tree_file = f"{base_name}_tree.dat"
        self.overflow_file = f"{base_name}_overflow.dat"
        self.metadata_file = f"{base_name}_meta.dat"
        
        self.metadata = ISAMMetadata()
        
        self._initialize()
        self._load_existing_index()
    
    def _initialize(self):
        """Crea archivos si no existen"""
        for file_path in [self.data_file, self.tree_file, 
                          self.overflow_file, self.metadata_file]:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    pass
    
    def _write_block(self, file_path: str, position: int, data: bytes) -> int:
        """Escribe bloque en disco"""
        with open(file_path, 'r+b' if position != -1 else 'ab') as f:
            if position == -1:
                position = f.seek(0, 2)
            else:
                f.seek(position)
            f.write(data)
        return position
    
    def _read_block(self, file_path: str, position: int, size: int) -> Optional[bytes]:
        """Lee bloque desde disco"""
        if position == -1 or not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'rb') as f:
                f.seek(position)
                data = f.read(size)
                return data if len(data) == size else None
        except:
            return None
    
    def _load_existing_index(self):
        """Carga índice existente desde disco"""
        try:
            if os.path.exists(self.metadata_file) and os.path.getsize(self.metadata_file) > 0:
                data = self._read_block(self.metadata_file, 0, os.path.getsize(self.metadata_file))
                if data:
                    self.metadata = ISAMMetadata.unpack(data)
        except:
            pass
    
    def _save_metadata(self):
        """Persiste metadatos"""
        data = self.metadata.pack()
        self._write_block(self.metadata_file, 0, data)
    
    def _write_node(self, node: Union[ISAMIntermediateNode, ISAMLeafNode], 
                    position: int = -1) -> int:
        """Escribe nodo en tree_file"""
        packed_data = node.pack()
        size_bytes = struct.pack('I', len(packed_data))
        full_data = size_bytes + packed_data
        
        return self._write_block(self.tree_file, position, full_data)
    
    def _read_node(self, position: int) -> Optional[Union[ISAMIntermediateNode, ISAMLeafNode]]:
        """Lee nodo desde tree_file"""
        if position == -1:
            return None
        
        try:
            size_data = self._read_block(self.tree_file, position, 4)
            if not size_data:
                return None
            
            size = struct.unpack('I', size_data)[0]
            node_data = self._read_block(self.tree_file, position + 4, size)
            if not node_data:
                return None
            
            obj = pickle.loads(node_data)
            if obj['is_leaf']:
                return ISAMLeafNode.unpack(node_data)
            else:
                return ISAMIntermediateNode.unpack(node_data)
        except:
            return None
    
    def _write_page(self, page: Page, position: int = -1) -> int:
        """Escribe página de datos"""
        packed_data = page.pack()
        
        if position == -1:
            position = self._write_block(self.data_file, -1, packed_data)
            self.metadata.num_pages += 1
        else:
            self._write_block(self.data_file, position, packed_data)
        
        return position
    
    def _read_page(self, position: int) -> Optional[Page]:
        """Lee página de datos"""
        if position == -1:
            return None
        
        page_size = Page.HEADER_SIZE + BLOCK_FACTOR * self.record_size
        data = self._read_block(self.data_file, position, page_size)
        
        if not data:
            return None
        
        try:
            return Page.unpack(data, self.table_schema, self.record_size)
        except:
            return None
    
    def _get_record_key(self, record: DynamicRecord) -> Any:
        """Extrae clave del registro"""
        return getattr(record, self.column_name, None)
    
    def _dict_to_record(self, data: Dict[str, Any]) -> DynamicRecord:
        """Convierte diccionario a DynamicRecord"""
        return DynamicRecord(self.table_schema, **data)
    
    def _record_to_dict(self, record: DynamicRecord) -> Dict[str, Any]:
        """Convierte DynamicRecord a diccionario"""
        result = {}
        for col in self.table_schema:
            result[col.name] = getattr(record, col.name, None)
        return result
    
    def build(self, records: List[Dict[str, Any]]):
        """
        Construye índice ISAM:
        - SIEMPRE inicia con 2 niveles (hojas + índice)
        - Se expande a 3 niveles si es necesario
        """
        if not records:
            return
        
        # Ordenar registros
        dynamic_records = [self._dict_to_record(rec) for rec in records]
        dynamic_records.sort(key=lambda r: self._get_record_key(r))
        
        # Crear páginas de datos (Nivel 0)
        leaf_nodes_data = []
        prev_page_pos = -1
        
        for i in range(0, len(dynamic_records), self.block_factor):
            page_records = dynamic_records[i:i + self.block_factor]
            page = Page(records=page_records, record_size=self.record_size)
            page_pos = self._write_page(page)
            
            if prev_page_pos != -1:
                prev_page = self._read_page(prev_page_pos)
                prev_page.next_page = page_pos
                self._write_page(prev_page, prev_page_pos)
            
            key = self._get_record_key(page_records[0])
            leaf_nodes_data.append({
                'key': key,
                'page_pos': page_pos
            })
            prev_page_pos = page_pos
        
        # Construir árbol dinámico
        self._build_dynamic_tree(leaf_nodes_data)
        
        # Actualizar metadatos
        self.metadata.num_records = len(dynamic_records)
        self.metadata.is_built = True
        self.metadata.num_leaf_nodes = len(leaf_nodes_data)
        self._save_metadata()
        
        print(f"✓ Índice ISAM construido: {self.metadata.num_levels} niveles, "
              f"{len(leaf_nodes_data)} hojas, {len(dynamic_records)} registros")
    
    def _build_dynamic_tree(self, leaf_data: List[Dict]):
        """
        Construye árbol con estrategia dinámica:
        - Inicial: 2 niveles (hojas + índice primario)
        - Expansión: 3 niveles si nodos intermedios > BLOCK_FACTOR
        """
        if not leaf_data:
            return
        
        print(f"→ Construyendo índice para {len(leaf_data)} hojas...")
        
        # NIVEL 1: Crear y enlazar nodos hoja
        leaf_positions = []
        for i, data in enumerate(leaf_data):
            leaf = ISAMLeafNode(
                key_value=data['key'],
                data_page_pointer=data['page_pos'],
                next_pointer=-1
            )
            pos = self._write_node(leaf)
            leaf_positions.append((pos, data['key']))
        
        # Enlazar hojas secuencialmente
        for i in range(len(leaf_positions) - 1):
            leaf = self._read_node(leaf_positions[i][0])
            leaf.next_pointer = leaf_positions[i + 1][0]
            self._write_node(leaf, leaf_positions[i][0])
        
        print(f"  Nivel 1: {len(leaf_positions)} nodos hoja")
        
        # NIVEL 2: Crear nodos intermedios agrupando hojas
        intermediate_nodes = []
        for i in range(0, len(leaf_positions), self.block_factor):
            group = leaf_positions[i:i + self.block_factor]
            
            separators = [item[1] for item in group[1:]]
            pointers = [item[0] for item in group]
            
            intermediate = ISAMIntermediateNode(
                values=separators,
                pointers=pointers,
                level=2
            )
            pos = self._write_node(intermediate)
            intermediate_nodes.append((pos, group[0][1]))
        
        print(f"  Nivel 2: {len(intermediate_nodes)} nodos intermedios")
        
        # DECISIÓN: ¿Necesitamos nivel 3?
        if len(intermediate_nodes) <= self.block_factor:
            # CASO 1: 2 NIVELES (un solo nodo intermedio es suficiente como raíz)
            self.metadata.root_pointer = intermediate_nodes[0][0]
            self.metadata.num_levels = 2
            print(f"  Estructura: 2 NIVELES (hojas + índice primario)")
        else:
            # CASO 2: 3 NIVELES (crear raíz superior)
            root = ISAMIntermediateNode(
                values=[item[1] for item in intermediate_nodes[1:]],
                pointers=[item[0] for item in intermediate_nodes],
                level=3
            )
            self.metadata.root_pointer = self._write_node(root)
            self.metadata.num_levels = 3
            print(f"  Estructura: 3 NIVELES (hojas + índice secundario + raíz)")
    
    def search(self, key: Any) -> List[Dict[str, Any]]:
        """Búsqueda exacta con navegación binaria"""
        if not self.metadata.is_built or self.metadata.root_pointer == -1:
            return []
        
        leaf_node = self._find_leaf_for_key_binary(key)
        if not leaf_node:
            return []
        
        page = self._read_page(leaf_node.data_page_pointer)
        if not page:
            return []
        
        results = []
        
        # Búsqueda binaria en página
        records_list = page.records
        first_idx = self._binary_search_in_list(records_list, key)
        
        if first_idx != -1:
            idx = first_idx
            while idx < len(records_list) and self._get_record_key(records_list[idx]) == key:
                results.append(self._record_to_dict(records_list[idx]))
                idx += 1
            
            idx = first_idx - 1
            while idx >= 0 and self._get_record_key(records_list[idx]) == key:
                results.insert(0, self._record_to_dict(records_list[idx]))
                idx -= 1
        
        # Incluir overflow
        if page.overflow_pointer != -1:
            overflow_records = self._read_overflow(page.overflow_pointer)
            for record in overflow_records:
                if self._get_record_key(record) == key:
                    results.append(self._record_to_dict(record))
        
        return results
    
    def _binary_search_in_list(self, records: List[DynamicRecord], key: Any) -> int:
        """Búsqueda binaria en lista ordenada"""
        left, right = 0, len(records) - 1
        result = -1
        
        while left <= right:
            mid = (left + right) // 2
            mid_key = self._get_record_key(records[mid])
            
            if mid_key == key:
                result = mid
                right = mid - 1
            elif mid_key < key:
                left = mid + 1
            else:
                right = mid - 1
        
        return result
    
    def _find_leaf_for_key_binary(self, key: Any) -> Optional[ISAMLeafNode]:
        """Navega el árbol hasta encontrar la hoja"""
        current_pos = self.metadata.root_pointer
        
        while current_pos != -1:
            node = self._read_node(current_pos)
            if not node:
                return None
            
            if node.is_leaf:
                return node
            
            child_index = node.find_child_index_binary(key)
            if child_index < len(node.pointers):
                current_pos = node.pointers[child_index]
            else:
                return None
        
        return None
    
    def rangeSearch(self, begin_key: Any, end_key: Any, 
                    begin_inclusive: bool = True, end_inclusive: bool = True) -> List[Dict[str, Any]]:
        """Búsqueda por rango"""
        if not self.metadata.is_built:
            return []
        
        results = []
        current_leaf = self._find_leaf_for_key_binary(begin_key)
        
        while current_leaf:
            page = self._read_page(current_leaf.data_page_pointer)
            if not page:
                break
            
            records_list = page.records
            
            # Búsqueda binaria del inicio
            left, right = 0, len(records_list) - 1
            start_idx = len(records_list)
            
            while left <= right:
                mid = (left + right) // 2
                mid_key = self._get_record_key(records_list[mid])
                
                condition = (mid_key >= begin_key) if begin_inclusive else (mid_key > begin_key)
                
                if condition:
                    start_idx = mid
                    right = mid - 1
                else:
                    left = mid + 1
            
            # Recolectar registros en rango
            for idx in range(start_idx, len(records_list)):
                key_val = self._get_record_key(records_list[idx])
                
                if end_inclusive:
                    if key_val > end_key:
                        return results
                else:
                    if key_val >= end_key:
                        return results
                
                start_ok = (key_val >= begin_key) if begin_inclusive else (key_val > begin_key)
                
                if start_ok:
                    results.append(self._record_to_dict(records_list[idx]))
            
            # Overflow
            if page.overflow_pointer != -1:
                overflow_records = self._read_overflow(page.overflow_pointer)
                for record in overflow_records:
                    key_val = self._get_record_key(record)
                    start_ok = (key_val >= begin_key) if begin_inclusive else (key_val > begin_key)
                    end_ok = (key_val <= end_key) if end_inclusive else (key_val < end_key)
                    
                    if start_ok and end_ok:
                        results.append(self._record_to_dict(record))
            
            if current_leaf.next_pointer != -1:
                current_leaf = self._read_node(current_leaf.next_pointer)
            else:
                break
        
        return results
    
    def add(self, record: Dict[str, Any]) -> bool:
        """Añade registro con manejo de overflow"""
        if not self.metadata.is_built:
            self.build([record])
            return True
        
        key = record[self.column_name]
        leaf_node = self._find_leaf_for_key_binary(key)
        
        if not leaf_node:
            return False
        
        page = self._read_page(leaf_node.data_page_pointer)
        if not page:
            return False
        
        dynamic_record = self._dict_to_record(record)
        
        if len(page.records) < self.block_factor:
            page.records.append(dynamic_record)
            page.records.sort(key=lambda r: self._get_record_key(r))
            self._write_page(page, leaf_node.data_page_pointer)
        else:
            overflow_pos = self._write_overflow(dynamic_record)
            
            if page.overflow_pointer == -1:
                page.overflow_pointer = overflow_pos
                self._write_page(page, leaf_node.data_page_pointer)
        
        self.metadata.num_records += 1
        self._save_metadata()
        return True
    
    def _write_overflow(self, record: DynamicRecord) -> int:
        """Escribe registro en archivo de overflow"""
        packed_data = record.pack()
        return self._write_block(self.overflow_file, -1, packed_data)
    
    def _read_overflow(self, position: int) -> List[DynamicRecord]:
        """Lee registros desde overflow"""
        records = []
        
        if position == -1:
            return records
        
        try:
            file_size = os.path.getsize(self.overflow_file)
            num_overflow_records = (file_size - position) // self.record_size
            
            for i in range(num_overflow_records):
                offset = position + (i * self.record_size)
                data = self._read_block(self.overflow_file, offset, self.record_size)
                
                if data and data != b'\x00' * self.record_size:
                    try:
                        record = DynamicRecord.unpack(self.table_schema, data)
                        if not record.deleted:
                            records.append(record)
                    except:
                        pass
        except:
            pass
        
        return records
    
    def remove(self, key: Any) -> bool:
        """Elimina registros con la clave (incluyendo overflow)"""
        if not self.metadata.is_built:
            return False
        
        leaf_node = self._find_leaf_for_key_binary(key)
        if not leaf_node:
            return False
        
        page = self._read_page(leaf_node.data_page_pointer)
        if not page:
            return False
        
        removed_count = 0
        
        original_count = len(page.records)
        page.records = [r for r in page.records if self._get_record_key(r) != key]
        removed_count += (original_count - len(page.records))
        
        # Filtrar overflow
        if page.overflow_pointer != -1:
            overflow_records = self._read_overflow(page.overflow_pointer)
            original_overflow = len(overflow_records)
            
            filtered_overflow = [r for r in overflow_records if self._get_record_key(r) != key]
            overflow_removed = original_overflow - len(filtered_overflow)
            removed_count += overflow_removed
            
            if overflow_removed > 0:
                if len(filtered_overflow) > 0:
                    new_overflow_pos = -1
                    for record in filtered_overflow:
                        if new_overflow_pos == -1:
                            new_overflow_pos = self._write_overflow(record)
                        else:
                            self._write_overflow(record)
                    page.overflow_pointer = new_overflow_pos
                else:
                    page.overflow_pointer = -1
        
        if removed_count > 0:
            self._write_page(page, leaf_node.data_page_pointer)
            self.metadata.num_records -= removed_count
            self._save_metadata()
            return True
        
        return False
    
    def getAllRecords(self) -> List[Dict[str, Any]]:
        """Obtiene todos los registros (páginas + overflow)"""
        if not self.metadata.is_built:
            return []
        
        results = []
        
        # Encontrar primera hoja
        current_pos = self.metadata.root_pointer
        first_leaf = None
        
        while current_pos != -1:
            node = self._read_node(current_pos)
            if not node:
                break
            
            if node.is_leaf:
                first_leaf = node
                break
            else:
                if node.pointers:
                    current_pos = node.pointers[0]
                else:
                    break
        
        if not first_leaf:
            return []
        
        # Recorrer todas las hojas
        current_leaf = first_leaf
        
        while current_leaf:
            page = self._read_page(current_leaf.data_page_pointer)
            if page:
                for record in page.records:
                    results.append(self._record_to_dict(record))
                
                if page.overflow_pointer != -1:
                    overflow_records = self._read_overflow(page.overflow_pointer)
                    for record in overflow_records:
                        results.append(self._record_to_dict(record))
            
            if current_leaf.next_pointer != -1:
                current_leaf = self._read_node(current_leaf.next_pointer)
            else:
                break
        
        return results
    
    def clear_all(self) -> int:
        """Limpia completamente el índice"""
        count = self.metadata.num_records
        
        for file_path in [self.data_file, self.tree_file, self.overflow_file]:
            with open(file_path, 'wb') as f:
                pass
        
        self.metadata = ISAMMetadata()
        self._save_metadata()
        
        return count
    
    def close(self):
        """Persiste metadatos finales"""
        self._save_metadata()