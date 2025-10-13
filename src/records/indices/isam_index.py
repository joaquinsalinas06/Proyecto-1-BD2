from typing import List, Dict, Any, Optional, Union
import os
import struct
import pickle
from .base_index import BaseIndex
from ..record import DynamicRecord
from ...parser.ast import ColumnDef

BLOCK_FACTOR = 4

class Page:
    """Página de datos optimizada con encadenamiento"""
    HEADER_FORMAT = 'iiq'  # size, next_page, overflow_pointer
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    SIZE_OF_PAGE = HEADER_SIZE + BLOCK_FACTOR * DynamicRecord.SIZE_OF_RECORD

    def __init__(self, records=None, next_page=-1, overflow_pointer=-1):
        self.records = records or []
        self.next_page = next_page
        self.overflow_pointer = overflow_pointer  # Puntero a página de overflow

    def pack(self):
        header_data = struct.pack(self.HEADER_FORMAT, len(self.records), 
                                  self.next_page, self.overflow_pointer)
        record_data = b''
        for record in self.records:
            record_data += record.pack()
        
        # Rellenar con registros vacíos
        for i in range(len(self.records), BLOCK_FACTOR):
            record_data += b'\x00' * DynamicRecord.SIZE_OF_RECORD
        
        return header_data + record_data

    @staticmethod
    def unpack(data: bytes):
        size, next_page, overflow_pointer = struct.unpack(
            Page.HEADER_FORMAT, data[:Page.HEADER_SIZE]
        )
        offset = Page.HEADER_SIZE
        records = []
        for i in range(size):
            record_data = data[offset: offset + DynamicRecord.SIZE_OF_RECORD]
            if record_data != b'\x00' * DynamicRecord.SIZE_OF_RECORD:
                records.append(DynamicRecord.unpack(record_data))
            offset += DynamicRecord.SIZE_OF_RECORD
        return Page(records, next_page, overflow_pointer)

class ISAMIntermediateNode:
    """Nodo intermedio optimizado con serialización eficiente"""
    def __init__(self, values=None, pointers=None, level=0):
        self.is_leaf = False
        self.values = values or []  # Lista flexible de claves
        self.pointers = pointers or []  # Lista flexible de punteros
        self.level = level  # Nivel en el árbol
        
    def pack(self):
        """Serializa el nodo usando pickle para flexibilidad"""
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
    
    def find_child_index(self, key: Any) -> int:
        """Encuentra el índice del hijo correspondiente a la clave"""
        for i, val in enumerate(self.values):
            if key < val:
                return i
        return len(self.values)

class ISAMLeafNode:
    """Nodo hoja optimizado con información adicional"""
    def __init__(self, key_value=None, data_page_pointer=-1, next_pointer=-1):
        self.is_leaf = True
        self.key_value = key_value
        self.data_page_pointer = data_page_pointer
        self.next_pointer = next_pointer
        
    def pack(self):
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
    """Metadatos del índice ISAM para recuperación rápida"""
    def __init__(self):
        self.root_pointer = -1
        self.num_levels = 0
        self.num_records = 0
        self.num_pages = 0
        self.next_page_position = 0
        self.next_node_position = 0
        self.is_built = False
        
    def pack(self):
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
    """Índice ISAM completamente persistente y optimizado"""
    
    def __init__(self, column_name: str, table_schema: List[ColumnDef], 
                 filename: str = None, block_factor: int = 4):
        super().__init__(column_name, filename)
        self.table_schema = table_schema
        self.block_factor = block_factor
        
        # Calcular tamaño de registro
        temp_record = DynamicRecord._build_format(table_schema)
        self.record_size = struct.calcsize(temp_record)
        
        # Archivos del sistema ISAM
        base_name = filename.replace('.dat', '') if filename else column_name
        self.data_file = f"{base_name}_data.dat"      # Páginas de datos
        self.tree_file = f"{base_name}_tree.dat"      # Nodos del árbol
        self.overflow_file = f"{base_name}_overflow.dat"  # Overflow
        self.metadata_file = f"{base_name}_meta.dat"  # Metadatos
        
        # Metadatos en memoria
        self.metadata = ISAMMetadata()
        
        # Cache de nodos (optimización)
        self.node_cache = {}
        self.cache_max_size = 50
        
        # Inicializar estructura
        self._initialize()
    
    def _initialize(self):
        """Inicializa o carga la estructura ISAM desde disco"""
        # Crear archivos si no existen
        for file_path in [self.data_file, self.tree_file, 
                          self.overflow_file, self.metadata_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    pass
        
        # Cargar metadatos
        self._load_metadata()
    
    def _load_metadata(self):
        """Carga metadatos desde disco"""
        if os.path.getsize(self.metadata_file) > 0:
            with open(self.metadata_file, 'rb') as f:
                data = f.read()
                self.metadata = ISAMMetadata.unpack(data)
    
    def _save_metadata(self):
        """Guarda metadatos en disco"""
        with open(self.metadata_file, 'wb') as f:
            f.write(self.metadata.pack())
    
    def _write_node(self, node: Union[ISAMIntermediateNode, ISAMLeafNode]) -> int:
        """Escribe un nodo en disco y devuelve su posición"""
        with open(self.tree_file, 'ab') as f:
            position = f.tell()
            packed_data = node.pack()
            # Escribir tamaño del nodo + datos
            f.write(struct.pack('I', len(packed_data)))
            f.write(packed_data)
        
        # Actualizar cache
        self.node_cache[position] = node
        if len(self.node_cache) > self.cache_max_size:
            # Eliminar entrada más antigua
            self.node_cache.pop(next(iter(self.node_cache)))
        
        return position
    
    def _read_node(self, position: int) -> Optional[Union[ISAMIntermediateNode, ISAMLeafNode]]:
        """Lee un nodo desde disco con cache"""
        if position == -1:
            return None
        
        # Verificar cache
        if position in self.node_cache:
            return self.node_cache[position]
        
        try:
            with open(self.tree_file, 'rb') as f:
                f.seek(position)
                size_data = f.read(4)
                if not size_data:
                    return None
                
                size = struct.unpack('I', size_data)[0]
                node_data = f.read(size)
                
                # Deserializar
                obj = pickle.loads(node_data)
                if obj['is_leaf']:
                    node = ISAMLeafNode.unpack(node_data)
                else:
                    node = ISAMIntermediateNode.unpack(node_data)
                
                # Actualizar cache
                self.node_cache[position] = node
                return node
        except Exception as e:
            print(f"Error reading node at {position}: {e}")
            return None
    
    def _write_page(self, page: Page, position: int = -1) -> int:
        """Escribe una página en disco (nueva o actualización)"""
        if position == -1:
            # Nueva página al final
            with open(self.data_file, 'ab') as f:
                position = f.tell()
                f.write(page.pack())
            self.metadata.num_pages += 1
        else:
            # Actualizar página existente
            with open(self.data_file, 'r+b') as f:
                f.seek(position)
                f.write(page.pack())
        
        return position
    
    def _read_page(self, position: int) -> Optional[Page]:
        """Lee una página desde disco"""
        if position == -1:
            return None
        
        try:
            with open(self.data_file, 'rb') as f:
                f.seek(position)
                data = f.read(Page.SIZE_OF_PAGE)
                if len(data) < Page.SIZE_OF_PAGE:
                    return None
                return Page.unpack(data)
        except Exception as e:
            print(f"Error reading page at {position}: {e}")
            return None
    
    def build(self, records: List[Dict[str, Any]]):
        """Construye el índice ISAM completo desde registros"""
        if not records:
            return
        
        print(f"Building ISAM index for {len(records)} records...")
        
        # Ordenar registros por clave
        sorted_records = sorted(records, key=lambda r: r[self.column_name])
        
        # Crear páginas de datos
        leaf_nodes = []
        prev_page_pos = -1
        
        for i in range(0, len(sorted_records), self.block_factor):
            page_records = sorted_records[i:i + self.block_factor]
            
            # Convertir a DynamicRecord
            dynamic_records = [
                DynamicRecord(self.table_schema, **rec) 
                for rec in page_records
            ]
            
            # Crear página
            page = Page(records=dynamic_records)
            page_pos = self._write_page(page)
            
            # Crear nodo hoja
            key = page_records[0][self.column_name]
            leaf_node = ISAMLeafNode(
                key_value=key,
                data_page_pointer=page_pos,
                next_pointer=-1
            )
            
            # Enlazar con página anterior
            if prev_page_pos != -1:
                prev_page = self._read_page(prev_page_pos)
                prev_page.next_page = page_pos
                self._write_page(prev_page, prev_page_pos)
            
            prev_page_pos = page_pos
            leaf_nodes.append(leaf_node)
        
        # Construir árbol desde nodos hoja
        self._build_tree_from_leaves(leaf_nodes)
        
        # Actualizar metadatos
        self.metadata.num_records = len(sorted_records)
        self.metadata.is_built = True
        self._save_metadata()
        
        print(f"ISAM index built successfully with {len(leaf_nodes)} leaf nodes")
    
    def _build_tree_from_leaves(self, leaf_nodes: List[ISAMLeafNode]):
        """Construye el árbol desde los nodos hoja hacia arriba"""
        if not leaf_nodes:
            return
        
        # Escribir nodos hoja y obtener posiciones
        leaf_positions = []
        for i, leaf in enumerate(leaf_nodes):
            # Enlazar nodos hoja
            if i < len(leaf_nodes) - 1:
                leaf.next_pointer = -1  # Se actualizará con la posición real
            pos = self._write_node(leaf)
            leaf_positions.append(pos)
        
        # Construir niveles superiores
        current_level = leaf_positions
        level_num = 0
        
        while len(current_level) > 1:
            parent_level = []
            
            # Crear nodos intermedios
            for i in range(0, len(current_level), self.block_factor):
                child_positions = current_level[i:i + self.block_factor]
                
                # Obtener claves de los hijos
                child_keys = []
                for pos in child_positions:
                    node = self._read_node(pos)
                    if node:
                        key = node.key_value if node.is_leaf else node.values[0]
                        child_keys.append(key)
                
                # Crear nodo intermedio
                parent = ISAMIntermediateNode(
                    values=child_keys[1:],  # Valores separadores
                    pointers=child_positions,
                    level=level_num + 1
                )
                
                parent_pos = self._write_node(parent)
                parent_level.append(parent_pos)
            
            current_level = parent_level
            level_num += 1
        
        # Establecer raíz
        if current_level:
            self.metadata.root_pointer = current_level[0]
            self.metadata.num_levels = level_num + 1
    
    def search(self, key: Any) -> List[Dict[str, Any]]:
        """Búsqueda optimizada con búsqueda binaria"""
        if not self.metadata.is_built or self.metadata.root_pointer == -1:
            return []
        
        # Navegar hasta el nodo hoja
        leaf_node = self._find_leaf_for_key(key)
        if not leaf_node:
            return []
        
        # Leer página de datos
        page = self._read_page(leaf_node.data_page_pointer)
        if not page:
            return []
        
        results = []
        
        # BÚSQUEDA BINARIA en página principal (registros ordenados)
        records_list = page.records
        left, right = 0, len(records_list) - 1
        
        # Encontrar primera ocurrencia con búsqueda binaria
        first_idx = -1
        while left <= right:
            mid = (left + right) // 2
            mid_key = records_list[mid].get(self.column_name)
            
            if mid_key == key:
                first_idx = mid
                right = mid - 1  # Buscar más a la izquierda
            elif mid_key < key:
                left = mid + 1
            else:
                right = mid - 1
        
        # Si encontramos, recoger todos los registros con la misma clave
        if first_idx != -1:
            # Hacia la derecha
            idx = first_idx
            while idx < len(records_list) and records_list[idx].get(self.column_name) == key:
                results.append(records_list[idx].to_dict())
                idx += 1
            
            # Hacia la izquierda (si hay duplicados antes)
            idx = first_idx - 1
            while idx >= 0 and records_list[idx].get(self.column_name) == key:
                results.append(records_list[idx].to_dict())
                idx -= 1
        
        # Buscar en overflow si existe
        if page.overflow_pointer != -1:
            overflow_records = self._read_overflow(page.overflow_pointer)
            for record in overflow_records:
                if record.get(self.column_name) == key:
                    results.append(record.to_dict())
        
        return results
    
    def _find_leaf_for_key(self, key: Any) -> Optional[ISAMLeafNode]:
        """Encuentra el nodo hoja correspondiente a una clave"""
        current_pos = self.metadata.root_pointer
        
        while current_pos != -1:
            node = self._read_node(current_pos)
            if not node:
                return None
            
            if node.is_leaf:
                return node
            
            # Nodo intermedio: encontrar hijo correcto
            child_index = node.find_child_index(key)
            if child_index < len(node.pointers):
                current_pos = node.pointers[child_index]
            else:
                return None
        
        return None
    
    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        """Búsqueda por rango optimizada"""
        if not self.metadata.is_built:
            return []
        
        results = []
        
        # Encontrar primer nodo hoja
        current_leaf = self._find_leaf_for_key(begin_key)
        
        while current_leaf:
            # Leer página
            page = self._read_page(current_leaf.data_page_pointer)
            if not page:
                break
            
            # Procesar registros
            for record in page.records:
                key_val = record.get(self.column_name)
                if begin_key <= key_val <= end_key:
                    results.append(record.to_dict())
                elif key_val > end_key:
                    return results
            
            # Procesar overflow
            if page.overflow_pointer != -1:
                overflow_records = self._read_overflow(page.overflow_pointer)
                for record in overflow_records:
                    key_val = record.get(self.column_name)
                    if begin_key <= key_val <= end_key:
                        results.append(record.to_dict())
            
            # Siguiente nodo hoja
            if current_leaf.next_pointer != -1:
                current_leaf = self._read_node(current_leaf.next_pointer)
            else:
                break
        
        return results
    
    def add(self, record: Dict[str, Any]) -> bool:
        """Añade un registro optimizado con manejo de overflow"""
        if not self.metadata.is_built:
            # Si no está construido, construir con este registro
            self.build([record])
            return True
        
        key = record[self.column_name]
        leaf_node = self._find_leaf_for_key(key)
        
        if not leaf_node:
            return False
        
        # Leer página
        page = self._read_page(leaf_node.data_page_pointer)
        if not page:
            return False
        
        # Crear DynamicRecord
        dynamic_record = DynamicRecord(self.table_schema, **record)
        
        if len(page.records) < self.block_factor:
            # Hay espacio en la página
            page.records.append(dynamic_record)
            page.records.sort(key=lambda r: r.get(self.column_name))
            self._write_page(page, leaf_node.data_page_pointer)
            self.metadata.num_records += 1
            self._save_metadata()
            return True
        else:
            # Página llena: escribir en overflow
            overflow_pos = self._write_overflow(dynamic_record)
            
            if page.overflow_pointer == -1:
                page.overflow_pointer = overflow_pos
                self._write_page(page, leaf_node.data_page_pointer)
            
            self.metadata.num_records += 1
            self._save_metadata()
            return True
    
    def _write_overflow(self, record: DynamicRecord) -> int:
        """Escribe un registro en el archivo de overflow"""
        with open(self.overflow_file, 'ab') as f:
            position = f.tell()
            f.write(record.pack())
        return position
    
    def _read_overflow(self, position: int) -> List[DynamicRecord]:
        """Lee registros del overflow"""
        records = []
        try:
            with open(self.overflow_file, 'rb') as f:
                f.seek(position)
                while True:
                    data = f.read(DynamicRecord.SIZE_OF_RECORD)
                    if len(data) < DynamicRecord.SIZE_OF_RECORD:
                        break
                    record = DynamicRecord.unpack(data)
                    records.append(record)
        except:
            pass
        return records
    
    def remove(self, key: Any) -> bool:
        """Elimina registros por clave con compactación"""
        if not self.metadata.is_built:
            return False
        
        leaf_node = self._find_leaf_for_key(key)
        if not leaf_node:
            return False
        
        page = self._read_page(leaf_node.data_page_pointer)
        if not page:
            return False
        
        original_count = len(page.records)
        
        # Filtrar registros
        page.records = [r for r in page.records if r.get(self.column_name) != key]
        
        if len(page.records) < original_count:
            self._write_page(page, leaf_node.data_page_pointer)
            self.metadata.num_records -= (original_count - len(page.records))
            self._save_metadata()
            return True
        
        return False
    
    def close(self):
        """Cierra el índice y limpia recursos"""
        self._save_metadata()
        self.node_cache.clear()
        print(f"ISAM index closed. Total records: {self.metadata.num_records}")