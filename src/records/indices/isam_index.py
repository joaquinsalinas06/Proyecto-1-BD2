"""
ESTRUCTURA DE 2 NIVELES:
---------------------------------------------------------------
Nivel 2 (Índice Primario): Árbol de nodos intermedios con claves separadoras
Nivel 1 (Índice Secundario): Nodos hoja que apuntan a páginas de datos
Nivel 0 (Datos): Páginas con registros ordenados + overflow encadenado
"""

from typing import List, Dict, Any, Optional, Union
import os
import struct
import pickle
import math
from .base_index import BaseIndex
from ..record import DynamicRecord
from ...parser.ast import ColumnDef

def calcular_BlockFactor(expected_records: Optional[int] = None) -> int:
    if expected_records is None:
        return 64
    
    optimal = int(math.sqrt(expected_records))

    power_of_2 = 2 ** round(math.log2(optimal))
    return max(32, min(512, power_of_2))


class Page:
    """
    Página de datos con encadenamiento.
    Estructura: [header: size(4) + next_page(4) + overflow_pointer(8) + overflow_count(4)] + [registros: block_factor * record_size]
    """
    HEADER_FORMAT = 'iiqi'  # size, next_page, overflow_pointer, overflow_count
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    def __init__(self, records=None, next_page=-1, overflow_pointer=-1, overflow_count=0, record_size=None, block_factor=64):
        self.records = records or []
        self.next_page = next_page
        self.overflow_pointer = overflow_pointer
        self.overflow_count = overflow_count  # Número de registros en overflow
        self.record_size = record_size
        self.block_factor = block_factor
    
    @property
    def SIZE_OF_PAGE(self):
        return self.HEADER_SIZE + self.block_factor * self.record_size

    def pack(self) -> bytes:
        """Empaqueta página completa en bytes para escritura en disco"""
        header_data = struct.pack(self.HEADER_FORMAT, len(self.records), 
                                  self.next_page, self.overflow_pointer, self.overflow_count)
        record_data = b''
        
        # Empaquetar registros existentes
        for record in self.records:
            record_data += record.pack()
        
        # Rellenar espacios vacíos con ceros
        empty_slots = self.block_factor - len(self.records)
        record_data += b'\x00' * (self.record_size * empty_slots)
        
        return header_data + record_data

    @staticmethod
    def unpack(data: bytes, table_schema: List[ColumnDef], record_size: int, block_factor: int = 64):
        """Desempaqueta bytes a objeto Page"""
        header_size = Page.HEADER_SIZE
        
        # Intentar leer con el nuevo formato (con overflow_count)
        if len(data) >= header_size:
            try:
                size, next_page, overflow_pointer, overflow_count = struct.unpack(
                    Page.HEADER_FORMAT, data[:header_size]
                )
            except struct.error:
                # Formato antiguo sin overflow_count - backward compatibility
                old_format = 'iiq'
                old_header_size = struct.calcsize(old_format)
                size, next_page, overflow_pointer = struct.unpack(
                    old_format, data[:old_header_size]
                )
                overflow_count = 0  # No tenemos conteo en formato antiguo
                header_size = old_header_size
        else:
            raise ValueError("Datos insuficientes para desempaquetar página")
            
        offset = header_size
        records = []
        
        for i in range(size):
            record_data = data[offset: offset + record_size]
            if record_data != b'\x00' * record_size:
                try:
                    record = DynamicRecord.unpack(table_schema, record_data)
                    if not record.deleted:  # Filtrar registros eliminados
                        records.append(record)
                except:
                    pass
            offset += record_size
            
        return Page(records, next_page, overflow_pointer, overflow_count, record_size, block_factor)


class ISAMIntermediateNode:
    """
    Nodo intermedio del árbol (Nivel 2).
    Contiene: [valores separadores] + [punteros a hijos]
    """
    def __init__(self, values=None, pointers=None, level=0):
        self.is_leaf = False
        self.values = values or []      # Claves separadoras
        self.pointers = pointers or []  # Posiciones de hijos en disco
        self.level = level              # Nivel en el árbol
        
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
        """
        Búsqueda binaria del índice del hijo correcto.
        Complejidad: O(log m) donde m = número de hijos
        """
        left, right = 0, len(self.values) - 1
        result = len(self.values)  # Por defecto, último hijo
        
        while left <= right:
            mid = (left + right) // 2
            if key < self.values[mid]:
                result = mid
                right = mid - 1
            else:
                left = mid + 1
        
        return result


class ISAMLeafNode:
    """
    Nodo hoja del árbol (Nivel 1).
    Apunta a: [página de datos] + [siguiente nodo hoja]
    """
    def __init__(self, key_value=None, data_page_pointer=-1, next_pointer=-1):
        self.is_leaf = True
        self.key_value = key_value              # Clave del primer registro
        self.data_page_pointer = data_page_pointer  # Posición de página de datos
        self.next_pointer = next_pointer        # Siguiente nodo hoja (enlace)
        
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
    """Metadatos persistentes para carga rápida del índice"""
    def __init__(self):
        self.root_pointer = -1      # Posición de raíz en tree_file
        self.num_levels = 0         # Niveles del árbol (mínimo 2)
        self.num_records = 0        # Total de registros
        self.num_pages = 0          # Páginas de datos
        self.num_leaf_nodes = 0     # Nodos hoja
        self.is_built = False       # ¿Índice construido?
        
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
  
    Todas las operaciones leen y escriben directamente en disco.
    No hay estructuras de datos en memoria RAM excepto metadatos mínimos.
    """
    
    def __init__(self, column_name: str, table_schema: List[ColumnDef], 
                 filename: str = None, block_factor: int = None,
                 is_primary: bool = False, primary_key_column: str = None,
                 expected_records: Optional[int] = None):
        super().__init__(column_name, filename, is_primary, primary_key_column)
        self.table_schema = table_schema
        if block_factor is None:
            block_factor = calcular_BlockFactor(expected_records) 
        self.block_factor = block_factor
        self.column_name = column_name
        
        self.io_stats = {
            'disk_reads': 0,
            'disk_writes': 0,
            'page_reads': 0,
            'page_writes': 0,
            'overflow_reads': 0,
            'overflow_writes': 0
        }
        
        # Calcular tamaño de registro dinámicamente
        self.record_format = DynamicRecord._build_format(table_schema)
        self.record_size = struct.calcsize(self.record_format)
        
        # Archivos del sistema ISAM
        base_name = filename.replace('.dat', '') if filename else column_name
        self.data_file = f"{base_name}_data.dat"
        self.tree_file = f"{base_name}_tree.dat"
        self.overflow_file = f"{base_name}_overflow.dat"
        self.metadata_file = f"{base_name}_meta.dat"
        
        # Metadatos en memoria (solo estructura pequeña)
        self.metadata = ISAMMetadata()
        
       
        self._initialize()
        self._load_existing_index()
    
    def _initialize(self):
        """Crea archivos si no existen - SOLO DISCO"""
        for file_path in [self.data_file, self.tree_file, 
                          self.overflow_file, self.metadata_file]:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    pass  # Crear archivo vacío
    
    def reset_io_stats(self):
        """Resetear contadores de I/O"""
        self.io_stats = {
            'disk_reads': 0,
            'disk_writes': 0,
            'page_reads': 0,
            'page_writes': 0,
            'overflow_reads': 0,
            'overflow_writes': 0
        }
    
    def get_io_stats(self) -> Dict[str, int]:
        """Obtener estadísticas de I/O actuales"""
        return self.io_stats.copy()
    
    def _write_block(self, file_path: str, position: int, data: bytes) -> int:
        """
        Escribe bloque de datos en posición específica - SOLO DISCO.
        Complejidad: O(1) - acceso directo con seek
        """
        self.io_stats['disk_writes'] += 1 
        with open(file_path, 'r+b' if position != -1 else 'ab') as f:
            if position == -1:
                position = f.seek(0, 2)  # Ir al final
            else:
                f.seek(position)
            f.write(data)
        return position
    
    def _read_block(self, file_path: str, position: int, size: int) -> Optional[bytes]:
        """
        Lee bloque de datos desde posición - SOLO DISCO.
        Complejidad: O(1) - acceso directo con seek
        """
        self.io_stats['disk_reads'] += 1  
        if position == -1 or not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'rb') as f:
                f.seek(position)
                data = f.read(size)
                return data if len(data) == size else None
        except Exception:
            return None
    
    def _load_existing_index(self):
        """Carga índice existente desde disco - CRÍTICO PARA PERSISTENCIA"""
        try:
            if os.path.exists(self.metadata_file) and os.path.getsize(self.metadata_file) > 0:
                data = self._read_block(self.metadata_file, 0, os.path.getsize(self.metadata_file))
                if data:
                    self.metadata = ISAMMetadata.unpack(data)
                   
        except Exception as e:
            pass
    
    def _save_metadata(self):
        """Persiste metadatos en disco"""
        data = self.metadata.pack()
        self._write_block(self.metadata_file, 0, data)
    
    def _write_node(self, node: Union[ISAMIntermediateNode, ISAMLeafNode], 
                    position: int = -1) -> int:
        """Escribe nodo en tree_file con tamaño variable"""
        packed_data = node.pack()
        size_bytes = struct.pack('I', len(packed_data))
        full_data = size_bytes + packed_data
        
        position = self._write_block(self.tree_file, position, full_data)

        
        return position
    
    def _read_node(self, position: int) -> Optional[Union[ISAMIntermediateNode, ISAMLeafNode]]:
        """
        Complejidad: O(1) - I/O directo
        """
        if position == -1:
            return None        
        try:
            # Leer tamaño del nodo
            size_data = self._read_block(self.tree_file, position, 4)
            if not size_data:
                return None
            
            size = struct.unpack('I', size_data)[0]
            
            # Leer datos del nodo
            node_data = self._read_block(self.tree_file, position + 4, size)
            if not node_data:
                return None
            
            # Deserializar
            obj = pickle.loads(node_data)
            if obj['is_leaf']:
                node = ISAMLeafNode.unpack(node_data)
            else:
                node = ISAMIntermediateNode.unpack(node_data)
            
            return node
            
        except Exception:
            return None
    
    def _write_page(self, page: Page, position: int = -1) -> int:
        """Escribe página completa en data_file"""
        self.io_stats['page_writes'] += 1 
        packed_data = page.pack()
        
        if position == -1:
            position = self._write_block(self.data_file, -1, packed_data)
            self.metadata.num_pages += 1
        else:
            self._write_block(self.data_file, position, packed_data)
        
        return position
    
    def _read_page(self, position: int) -> Optional[Page]:
        """
        Lee página desde data_file - DIRECTO A DISCO
        Complejidad: O(1) - acceso directo
        """
        self.io_stats['page_reads'] += 1 
        if position == -1:
            return None
        
        page_size = Page.HEADER_SIZE + self.block_factor * self.record_size
        data = self._read_block(self.data_file, position, page_size)
        
        if not data:
            return None
        
        try:
            return Page.unpack(data, self.table_schema, self.record_size, self.block_factor)
        except Exception:
            return None
    
    def _get_record_key(self, record: DynamicRecord) -> Any:
        """Extrae clave de indexación del registro"""
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
    
    def bulk_load(self, records: List[Dict[str, Any]]) -> bool:
        self.build(records)
        return True


    def build(self, records: List[Dict[str, Any]]):
        """
        Construye índice ISAM de 2 niveles desde registros.
        
        ALGORITMO:
        ---------
        1. Ordenar registros por clave: O(n log n)
        2. Crear páginas de datos (nivel 0): O(n)
        3. Crear nodos hoja (nivel 1): O(n/BLOCK_FACTOR)
        4. Crear nodos intermedios (nivel 2): O(n/BLOCK_FACTOR²)
        
        Complejidad total: O(n log n)
        """
        if not records:
            return
        
        dynamic_records = [self._dict_to_record(rec) for rec in records]
        dynamic_records.sort(key=lambda r: self._get_record_key(r))
        
        leaf_nodes_data = []
        prev_page_pos = -1
        
        for i in range(0, len(dynamic_records), self.block_factor):
            page_records = dynamic_records[i:i + self.block_factor]
            page = Page(records=page_records, record_size=self.record_size, block_factor=self.block_factor)
            page_pos = self._write_page(page)
            
            # Enlazar con página anterior
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
        
        self._build_two_level_tree(leaf_nodes_data)
        
        self.metadata.num_records = len(dynamic_records)
        self.metadata.is_built = True
        self.metadata.num_leaf_nodes = len(leaf_nodes_data)
        self._save_metadata()
        
    def _build_two_level_tree(self, leaf_data: List[Dict]):
        """
        Construye árbol de exactamente 2 niveles.
        Todas las escrituras van directo a disco.
        """
        if not leaf_data:
            return
        

        # NIVEL 1: Crear nodos hoja

        leaf_positions = []
        
        for i, data in enumerate(leaf_data):
            leaf = ISAMLeafNode(
                key_value=data['key'],
                data_page_pointer=data['page_pos'],
                next_pointer=-1
            )
            pos = self._write_node(leaf)
            leaf_positions.append((pos, data['key']))
        
        # Enlazar nodos hoja secuencialmente
        for i in range(len(leaf_positions) - 1):
            leaf = self._read_node(leaf_positions[i][0])
            leaf.next_pointer = leaf_positions[i + 1][0]
            self._write_node(leaf, leaf_positions[i][0])
        
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
        
        if len(intermediate_nodes) == 1:
            self.metadata.root_pointer = intermediate_nodes[0][0]
            self.metadata.num_levels = 2
        else:
            root = ISAMIntermediateNode(
                values=[item[1] for item in intermediate_nodes[1:]],
                pointers=[item[0] for item in intermediate_nodes],
                level=3
            )
            self.metadata.root_pointer = self._write_node(root)
            self.metadata.num_levels = 3
    
    # ====================================================================
    #                  BÚSQUEDA (CON BÚSQUEDA BINARIA)
    # ====================================================================
    
    def search(self, key: Any) -> List[Dict[str, Any]]:
        """
        Búsqueda por clave exacta con búsqueda binaria en todos los niveles.
        
        ALGORITMO:
        ---------
        1. Navegar árbol con búsqueda binaria: O(log m) por nivel
        2. Búsqueda binaria en página: O(log BLOCK_FACTOR)
        3. Búsqueda lineal en overflow: O(k) donde k = registros overflow
        
        Complejidad: O(log n + k)
        """
        if not self.metadata.is_built or self.metadata.root_pointer == -1:
            return []
        
        leaf_node = self._find_leaf_for_key_binary(key)
        if not leaf_node:
            return []
        
        page = self._read_page(leaf_node.data_page_pointer)
        if not page:
            return []
        
        results = []
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
        
        if page.overflow_pointer != -1:
            overflow_records = self._read_overflow(page.overflow_pointer, page.overflow_count)
            for record in overflow_records:
                if self._get_record_key(record) == key:
                    results.append(self._record_to_dict(record))
        
        return results
    
    def _binary_search_in_list(self, records: List[DynamicRecord], key: Any) -> int:
        """
        Búsqueda binaria en lista de registros ordenados.
        Retorna índice de la primera ocurrencia o -1.
        
        Complejidad: O(log n)
        """
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
        """
        Navega el árbol hasta encontrar la hoja usando búsqueda binaria.
        
        Complejidad: O(log₂(páginas))
        """
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
        """
        Búsqueda por rango con búsqueda binaria e inclusión de overflow.
        
        ALGORITMO:
        ---------
        1. Encontrar primera hoja con begin_key: O(log n)
        2. Recorrer hojas secuencialmente hasta end_key: O(k/BLOCK_FACTOR)
        3. Por cada página: búsqueda binaria del inicio: O(log BLOCK_FACTOR)
        4. Incluir overflow de cada página: O(m)
        
        Complejidad: O(log n + k) donde k = registros en rango
        """
        if not self.metadata.is_built:
            return []
        
        results = []
        
        
        current_leaf = self._find_leaf_for_key_binary(begin_key)
        
        while current_leaf:
            page = self._read_page(current_leaf.data_page_pointer)
            if not page:
                break
            
            records_list = page.records
            
            # 3. Búsqueda binaria del inicio del rango en esta página
            left, right = 0, len(records_list) - 1
            start_idx = len(records_list)
            
            while left <= right:
                mid = (left + right) // 2
                mid_key = self._get_record_key(records_list[mid])
                
                if begin_inclusive:
                    condition = mid_key >= begin_key
                else:
                    condition = mid_key > begin_key
                
                if condition:
                    start_idx = mid
                    right = mid - 1
                else:
                    left = mid + 1
            
            for idx in range(start_idx, len(records_list)):
                key_val = self._get_record_key(records_list[idx])
                
                if end_inclusive:
                    if key_val > end_key:
                        return results
                else:
                    if key_val >= end_key:
                        return results
                
                if begin_inclusive:
                    start_ok = key_val >= begin_key
                else:
                    start_ok = key_val > begin_key
                
                if start_ok:
                    results.append(self._record_to_dict(records_list[idx]))
            
            if page.overflow_pointer != -1:
                overflow_records = self._read_overflow(page.overflow_pointer, page.overflow_count)
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
        """
        Añade registro con manejo de overflow (sin reconstrucción).
        
        ALGORITMO:
        ---------
        1. Si índice no construido: construir con este registro
        2. Encontrar hoja correspondiente: O(log n)
        3. Si hay espacio en página: insertar ordenado
        4. Si página llena: escribir en overflow
        
        Complejidad: O(log n)
        """
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
            page.overflow_count += 1  # Incrementar contador de overflow
            self._write_page(page, leaf_node.data_page_pointer)
        
        self.metadata.num_records += 1
        self._save_metadata()
        return True
    
    def _write_overflow(self, record: DynamicRecord) -> int:
        """
        Escribe registro en archivo de overflow.
        Los registros en overflow no están ordenados (inserción simple).
        
        Complejidad: O(1)
        """
        self.io_stats['overflow_writes'] += 1  
        packed_data = record.pack()
        return self._write_block(self.overflow_file, -1, packed_data)
    
    def _read_overflow(self, position: int, overflow_count: int = None) -> List[DynamicRecord]:
        """
        Lee registros desde la posición de overflow.
        
        Args:
            position: Posición en el archivo de overflow
            overflow_count: Número de registros en overflow (None para leer hasta EOF - backward compatibility)
        
        Complejidad: O(k) donde k = registros en overflow
        """
        self.io_stats['overflow_reads'] += 1 
        records = []
        
        if position == -1:
            return records
        
        try:
            if overflow_count is None or overflow_count == 0:
                # Formato antiguo sin count - leer hasta el final (backward compatibility)
                file_size = os.path.getsize(self.overflow_file)
                num_overflow_records = (file_size - position) // self.record_size
            else:
                # Formato nuevo con count
                num_overflow_records = overflow_count
            
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
        except Exception as e:
            pass
        
        return records
    

    def remove(self, key: Any) -> bool:
        """
        Elimina todos los registros con la clave (incluyendo overflow).
        
        ALGORITMO:
        ---------
        1. Encontrar hoja: O(log n)
        2. Filtrar registros en página: O(BLOCK_FACTOR)
        3. Filtrar registros en overflow: O(k)
        4. Reescribir página y overflow
        
        Complejidad: O(log n + k)
        """
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
        removed_from_page = original_count - len(page.records)
        removed_count += removed_from_page
        
        if page.overflow_pointer != -1:
            overflow_records = self._read_overflow(page.overflow_pointer, page.overflow_count)
            original_overflow = len(overflow_records)
            
            filtered_overflow = [r for r in overflow_records if self._get_record_key(r) != key]
            overflow_removed = original_overflow - len(filtered_overflow)
            removed_count += overflow_removed
            
            if overflow_removed > 0:
                if len(filtered_overflow) > 0:
                    self.io_stats['overflow_writes'] += 1  
                    new_overflow_pos = -1
                    with open(self.overflow_file, 'ab') as f:
                        new_overflow_pos = f.tell()
                        for record in filtered_overflow:
                            packed_data = record.pack()
                            f.write(packed_data)
                    
                    page.overflow_pointer = new_overflow_pos
                    page.overflow_count = len(filtered_overflow)
                else:
                    page.overflow_pointer = -1
                    page.overflow_count = 0
        
        if removed_count > 0:
            self._write_page(page, leaf_node.data_page_pointer)
            self.metadata.num_records -= removed_count
            self._save_metadata()
            return True
        
        return False
    
    def getAllRecords(self) -> List[Dict[str, Any]]:
        """
        Obtiene TODOS los registros del índice (páginas + overflow).
        
        ALGORITMO:
        ---------
        1. Encontrar primera hoja navegando desde raíz
        2. Recorrer todas las hojas secuencialmente
        3. Por cada hoja: leer página + overflow
        
        Complejidad: O(n)
        """
        if not self.metadata.is_built:
            return []
        
        results = []
        
        # Encontrar primera hoja
        current_pos = self.metadata.root_pointer
        first_leaf = None
        
        while current_pos != -1:
            node = self._read_node(current_pos)  # Lectura de disco
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
            page = self._read_page(current_leaf.data_page_pointer)  # Lectura de disco
            if page:
                for record in page.records:
                    results.append(self._record_to_dict(record))
                
                if page.overflow_pointer != -1:
                    overflow_records = self._read_overflow(page.overflow_pointer, page.overflow_count)
                    for record in overflow_records:
                        results.append(self._record_to_dict(record))
            
            if current_leaf.next_pointer != -1:
                current_leaf = self._read_node(current_leaf.next_pointer)  # Lectura de disco
            else:
                break
        
        return results
    
    def clear_all(self) -> int:
        """
        Limpia completamente el índice (trunca todos los archivos).
        
        Complejidad: O(1) - solo truncar archivos
        """
        count = self.metadata.num_records
        
        # Truncar todos los archivos
        self.io_stats['disk_writes'] += 3 
        for file_path in [self.data_file, self.tree_file, self.overflow_file]:
            with open(file_path, 'wb') as f:
                pass
        
        # Resetear metadatos
        self.metadata = ISAMMetadata()
        self._save_metadata()
        
        
        return count
    
    def close(self):
        """
        Solo persiste metadatos finales.
        """
        self._save_metadata()

