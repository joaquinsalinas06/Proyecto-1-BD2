"""



ESTRUCTURA DE 2 NIVELES:
------------------------
Nivel 2 (Índice Primario): Árbol de nodos intermedios con claves separadoras
Nivel 1 (Índice Secundario): Nodos hoja que apuntan a páginas de datos
Nivel 0 (Datos): Páginas con registros ordenados + overflow encadenado


"""

from typing import List, Dict, Any, Optional, Union
import os
import struct
import pickle
from .base_index import BaseIndex
from ..record import DynamicRecord
from ...parser.ast import ColumnDef

BLOCK_FACTOR = 4  # Registros por página


class Page:
    """
    Página de datos con encadenamiento.
    Estructura: [header: size(4) + next_page(4) + overflow(8)] + [registros: BLOCK_FACTOR * record_size]
    """
    HEADER_FORMAT = 'iiq'  # int size, int next_page, long long overflow_pointer
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
        """Empaqueta página completa en bytes para escritura en disco"""
        header_data = struct.pack(self.HEADER_FORMAT, len(self.records), 
                                  self.next_page, self.overflow_pointer)
        record_data = b''
        
        # Empaquetar registros existentes
        for record in self.records:
            record_data += record.pack()
        
        # Rellenar espacios vacíos con ceros
        empty_slots = BLOCK_FACTOR - len(self.records)
        record_data += b'\x00' * (self.record_size * empty_slots)
        
        return header_data + record_data

    @staticmethod
    def unpack(data: bytes, table_schema: List[ColumnDef], record_size: int):
        """Desempaqueta bytes a objeto Page"""
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
                    if not record.deleted:  # Filtrar registros eliminados
                        records.append(record)
                except:
                    pass
            offset += record_size
            
        return Page(records, next_page, overflow_pointer, record_size)


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
 
    
    def __init__(self, column_name: str, table_schema: List[ColumnDef], 
                 filename: str = None, block_factor: int = 4,
                 is_primary: bool = False, primary_key_column: str = None):
        super().__init__(column_name, filename, is_primary, primary_key_column)
        self.table_schema = table_schema
        self.block_factor = block_factor
        self.column_name = column_name
        
        # Calcular tamaño de registro dinámicamente
        self.record_format = DynamicRecord._build_format(table_schema)
        self.record_size = struct.calcsize(self.record_format)
        
        # Archivos del sistema ISAM
        base_name = filename.replace('.dat', '') if filename else column_name
        self.data_file = f"{base_name}_data.dat"
        self.tree_file = f"{base_name}_tree.dat"
        self.overflow_file = f"{base_name}_overflow.dat"
        self.metadata_file = f"{base_name}_meta.dat"
        
        # Metadatos en memoria
        self.metadata = ISAMMetadata()
        
        # Cache de nodos (LRU simple)
        self.node_cache = {}
        self.cache_max_size = 100
        
        # Inicializar y cargar si existe
        self._initialize()
        self._load_existing_index()
    
    # ====================================================================
    #                      OPERACIONES DE DISCO
    # ====================================================================
    
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
    
    def _write_block(self, file_path: str, position: int, data: bytes) -> int:
        """
        Escribe bloque de datos en posición específica - SOLO DISCO.
        Complejidad: O(1) - acceso directo con seek
        """
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
        if position == -1 or not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'rb') as f:
                f.seek(position)
                data = f.read(size)
                return data if len(data) == size else None
        except Exception as e:
            print(f"Error leyendo bloque en {position}: {e}")
            return None
    
    def _load_existing_index(self):
        """Carga índice existente desde disco - CRÍTICO PARA PERSISTENCIA"""
        try:
            if os.path.exists(self.metadata_file) and os.path.getsize(self.metadata_file) > 0:
                data = self._read_block(self.metadata_file, 0, os.path.getsize(self.metadata_file))
                if data:
                    self.metadata = ISAMMetadata.unpack(data)
                    print(f"✓ ISAM cargado: {self.metadata.num_records} registros, "
                          f"{self.metadata.num_levels} niveles, "
                          f"{self.metadata.num_leaf_nodes} hojas")
        except Exception as e:
            print(f"Iniciando nuevo índice ISAM: {e}")
    
    def _save_metadata(self):
        """Persiste metadatos en disco"""
        data = self.metadata.pack()
        self._write_block(self.metadata_file, 0, data)
    
    # ====================================================================
    #                   OPERACIONES DE NODOS Y PÁGINAS
    # ====================================================================
    
    def _write_node(self, node: Union[ISAMIntermediateNode, ISAMLeafNode], 
                    position: int = -1) -> int:
        """Escribe nodo en tree_file con tamaño variable"""
        packed_data = node.pack()
        size_bytes = struct.pack('I', len(packed_data))
        full_data = size_bytes + packed_data
        
        position = self._write_block(self.tree_file, position, full_data)
        
        # Actualizar cache
        self.node_cache[position] = node
        if len(self.node_cache) > self.cache_max_size:
            self.node_cache.pop(next(iter(self.node_cache)))
        
        return position
    
    def _read_node(self, position: int) -> Optional[Union[ISAMIntermediateNode, ISAMLeafNode]]:
        """
        Lee nodo desde tree_file con cache.
        Complejidad: O(1) con cache, O(1) sin cache (I/O directo)
        """
        if position == -1:
            return None
        
        # Verificar cache
        if position in self.node_cache:
            return self.node_cache[position]
        
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
            
            # Actualizar cache
            self.node_cache[position] = node
            return node
            
        except Exception as e:
            print(f"Error leyendo nodo en {position}: {e}")
            return None
    
    def _write_page(self, page: Page, position: int = -1) -> int:
        """Escribe página completa en data_file"""
        packed_data = page.pack()
        
        if position == -1:
            position = self._write_block(self.data_file, -1, packed_data)
            self.metadata.num_pages += 1
        else:
            self._write_block(self.data_file, position, packed_data)
        
        return position
    
    def _read_page(self, position: int) -> Optional[Page]:
        """
        Lee página desde data_file.
        Complejidad: O(1) - acceso directo
        """
        if position == -1:
            return None
        
        page_size = Page.HEADER_SIZE + BLOCK_FACTOR * self.record_size
        data = self._read_block(self.data_file, position, page_size)
        
        if not data:
            return None
        
        try:
            return Page.unpack(data, self.table_schema, self.record_size)
        except Exception as e:
            print(f"Error desempaquetando página: {e}")
            return None
    
    # ====================================================================
    #                    UTILIDADES DE REGISTROS
    # ====================================================================
    
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
    
    # ====================================================================
    #              CONSTRUCCIÓN DEL ÍNDICE (2 NIVELES)
    # ====================================================================
    
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
        
        print(f"\n{'='*60}")
        print(f"CONSTRUYENDO ÍNDICE ISAM DE 2 NIVELES")
        print(f"{'='*60}")
        print(f"Registros a indexar: {len(records)}")
        
        # 1. Convertir y ordenar registros
        dynamic_records = [self._dict_to_record(rec) for rec in records]
        dynamic_records.sort(key=lambda r: self._get_record_key(r))
        
        # 2. Crear páginas de datos (Nivel 0)
        leaf_nodes_data = []
        prev_page_pos = -1
        
        print(f"Creando páginas de datos (BLOCK_FACTOR={self.block_factor})...")
        for i in range(0, len(dynamic_records), self.block_factor):
            page_records = dynamic_records[i:i + self.block_factor]
            page = Page(records=page_records, record_size=self.record_size)
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
        
        print(f"✓ {len(leaf_nodes_data)} páginas creadas")
        
        # 3. Construir árbol de 2 niveles
        self._build_two_level_tree(leaf_nodes_data)
        
        # 4. Actualizar metadatos
        self.metadata.num_records = len(dynamic_records)
        self.metadata.is_built = True
        self.metadata.num_leaf_nodes = len(leaf_nodes_data)
        self._save_metadata()
        
        print(f"\n{'='*60}")
        print(f"✓ ÍNDICE ISAM CONSTRUIDO EXITOSAMENTE")
        print(f"{'='*60}")
        print(f"Niveles del árbol: {self.metadata.num_levels}")
        print(f"Nodos hoja (nivel 1): {self.metadata.num_leaf_nodes}")
        print(f"Páginas de datos (nivel 0): {self.metadata.num_pages}")
        print(f"Registros totales: {self.metadata.num_records}")
        print(f"{'='*60}\n")
    
    def _build_two_level_tree(self, leaf_data: List[Dict]):
        """
        Construye árbol de exactamente 2 niveles.
        
        NIVEL 1 (hojas): Apuntan a páginas de datos
        NIVEL 2 (raíz/intermedios): Apuntan a nodos hoja
        
        Complejidad: O(n/BLOCK_FACTOR)
        """
        if not leaf_data:
            return
        
        print(f"\nConstruyendo estructura de 2 niveles...")
        
        # NIVEL 1: Crear nodos hoja
        print(f"Nivel 1: Creando {len(leaf_data)} nodos hoja...")
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
        
        print(f"✓ {len(leaf_positions)} nodos hoja creados y enlazados")
        
        # NIVEL 2: Crear nodos intermedios
        print(f"Nivel 2: Creando nodos intermedios...")
        intermediate_nodes = []
        
        for i in range(0, len(leaf_positions), self.block_factor):
            group = leaf_positions[i:i + self.block_factor]
            
            # Claves separadoras (desde el segundo hijo)
            separators = [item[1] for item in group[1:]]
            pointers = [item[0] for item in group]
            
            intermediate = ISAMIntermediateNode(
                values=separators,
                pointers=pointers,
                level=2
            )
            
            pos = self._write_node(intermediate)
            intermediate_nodes.append((pos, group[0][1]))
        
        print(f"✓ {len(intermediate_nodes)} nodos intermedios creados")
        
        # Establecer raíz
        if len(intermediate_nodes) == 1:
            # Caso simple: un solo nodo intermedio es la raíz
            self.metadata.root_pointer = intermediate_nodes[0][0]
            self.metadata.num_levels = 2
        else:
            # Múltiples nodos intermedios: crear raíz superior
            print(f"Creando raíz superior para {len(intermediate_nodes)} nodos...")
            root = ISAMIntermediateNode(
                values=[item[1] for item in intermediate_nodes[1:]],
                pointers=[item[0] for item in intermediate_nodes],
                level=3
            )
            self.metadata.root_pointer = self._write_node(root)
            self.metadata.num_levels = 3
        
        print(f"✓ Raíz establecida en posición {self.metadata.root_pointer}")
    
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
        
        # 1. Encontrar nodo hoja con búsqueda binaria en árbol
        leaf_node = self._find_leaf_for_key_binary(key)
        if not leaf_node:
            return []
        
        # 2. Leer página de datos
        page = self._read_page(leaf_node.data_page_pointer)
        if not page:
            return []
        
        results = []
        
        # 3. Búsqueda binaria en página ordenada
        records_list = page.records
        first_idx = self._binary_search_in_list(records_list, key)
        
        if first_idx != -1:
            # Recoger todos los registros con la misma clave
            idx = first_idx
            while idx < len(records_list) and self._get_record_key(records_list[idx]) == key:
                results.append(self._record_to_dict(records_list[idx]))
                idx += 1
            
            # Revisar hacia atrás por duplicados
            idx = first_idx - 1
            while idx >= 0 and self._get_record_key(records_list[idx]) == key:
                results.insert(0, self._record_to_dict(records_list[idx]))
                idx -= 1
        
        # 4. INCLUIR OVERFLOW: Búsqueda lineal en overflow
        if page.overflow_pointer != -1:
            overflow_records = self._read_overflow(page.overflow_pointer)
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
                right = mid - 1  # Buscar más a la izquierda
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
            
            # Búsqueda binaria del hijo correcto
            child_index = node.find_child_index_binary(key)
            if child_index < len(node.pointers):
                current_pos = node.pointers[child_index]
            else:
                return None
        
        return None
    
    # ====================================================================
    #                    BÚSQUEDA POR RANGO
    # ====================================================================
    
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
        
        # 1. Encontrar primera hoja que podría contener begin_key
        current_leaf = self._find_leaf_for_key_binary(begin_key)
        
        while current_leaf:
            # 2. Leer página
            page = self._read_page(current_leaf.data_page_pointer)
            if not page:
                break
            
            records_list = page.records
            
            # 3. Búsqueda binaria del inicio del rango en esta página
            left, right = 0, len(records_list) - 1
            start_idx = len(records_list)  # Por defecto, después del final
            
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
            
            # 4. Procesar registros desde start_idx
            for idx in range(start_idx, len(records_list)):
                key_val = self._get_record_key(records_list[idx])
                
                # Verificar si pasamos el rango
                if end_inclusive:
                    if key_val > end_key:
                        return results
                else:
                    if key_val >= end_key:
                        return results
                
                # Verificar si está en el rango
                if begin_inclusive:
                    start_ok = key_val >= begin_key
                else:
                    start_ok = key_val > begin_key
                
                if start_ok:
                    results.append(self._record_to_dict(records_list[idx]))
            
            # 5. INCLUIR OVERFLOW: Procesar registros en overflow
            if page.overflow_pointer != -1:
                overflow_records = self._read_overflow(page.overflow_pointer)
                for record in overflow_records:
                    key_val = self._get_record_key(record)
                    
                    # Verificar condiciones del rango
                    start_ok = (key_val >= begin_key) if begin_inclusive else (key_val > begin_key)
                    end_ok = (key_val <= end_key) if end_inclusive else (key_val < end_key)
                    
                    if start_ok and end_ok:
                        results.append(self._record_to_dict(record))
            
            # 6. Avanzar al siguiente nodo hoja
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
        
        # Leer página
        page = self._read_page(leaf_node.data_page_pointer)
        if not page:
            return False
        
        dynamic_record = self._dict_to_record(record)
        
        if len(page.records) < self.block_factor:
            # HAY ESPACIO: Insertar en página ordenada
            page.records.append(dynamic_record)
            page.records.sort(key=lambda r: self._get_record_key(r))
            self._write_page(page, leaf_node.data_page_pointer)
        else:
            # PÁGINA LLENA: Escribir en overflow
            overflow_pos = self._write_overflow(dynamic_record)
            
            if page.overflow_pointer == -1:
                # Primera vez que se usa overflow
                page.overflow_pointer = overflow_pos
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
        packed_data = record.pack()
        return self._write_block(self.overflow_file, -1, packed_data)
    
    def _read_overflow(self, position: int) -> List[DynamicRecord]:
        """
        Lee TODOS los registros desde la posición de overflow hasta el final.
        
        Complejidad: O(k) donde k = registros en overflow
        """
        records = []
        
        if position == -1:
            return records
        
        try:
            # Calcular cuántos registros hay en overflow
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
        except Exception as e:
            print(f"Error leyendo overflow en {position}: {e}")
        
        return records
    
    # ====================================================================
    #                    ELIMINACIÓN CON OVERFLOW
    # ====================================================================
    
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
        
        # 1. Filtrar registros en página principal
        original_count = len(page.records)
        page.records = [r for r in page.records if self._get_record_key(r) != key]
        removed_count += (original_count - len(page.records))
        
        # 2. INCLUIR OVERFLOW: Filtrar registros en overflow
        if page.overflow_pointer != -1:
            overflow_records = self._read_overflow(page.overflow_pointer)
            original_overflow = len(overflow_records)
            
            # Filtrar overflow
            filtered_overflow = [r for r in overflow_records if self._get_record_key(r) != key]
            overflow_removed = original_overflow - len(filtered_overflow)
            removed_count += overflow_removed
            
            # Reescribir overflow si se eliminaron registros
            if overflow_removed > 0:
                if len(filtered_overflow) > 0:
                    # Reescribir overflow filtrado
                    new_overflow_pos = -1
                    for record in filtered_overflow:
                        if new_overflow_pos == -1:
                            new_overflow_pos = self._write_overflow(record)
                        else:
                            self._write_overflow(record)
                    page.overflow_pointer = new_overflow_pos
                else:
                    # No quedan registros en overflow
                    page.overflow_pointer = -1
        
        # 3. Actualizar página si hubo cambios
        if removed_count > 0:
            self._write_page(page, leaf_node.data_page_pointer)
            self.metadata.num_records -= removed_count
            self._save_metadata()
            return True
        
        return False
    
    # ====================================================================
    #                    OPERACIONES ADICIONALES
    # ====================================================================
    
    def getAllRecords(self) -> List[Dict[str, Any]]:
        """
        Obtiene TODOS los registros del índice (páginas + overflow).
        
        ALGORITMO:
        ---------
        1. Encontrar primera hoja navegando desde raíz
        2. Recorrer todas las hojas secuencialmente
        3. Por cada hoja: leer página + overflow
        
        Complejidad: O(n) - debe leer todos los registros
        """
        if not self.metadata.is_built:
            return []
        
        results = []
        
        # 1. Encontrar primera hoja (ir siempre al primer hijo)
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
                # Ir al primer hijo (índice 0)
                if node.pointers:
                    current_pos = node.pointers[0]
                else:
                    break
        
        if not first_leaf:
            return []
        
        # 2. Recorrer todas las hojas secuencialmente
        current_leaf = first_leaf
        
        while current_leaf:
            # Leer página de datos
            page = self._read_page(current_leaf.data_page_pointer)
            if page:
                # Agregar registros de la página
                for record in page.records:
                    results.append(self._record_to_dict(record))
                
                # INCLUIR OVERFLOW: Agregar registros en overflow
                if page.overflow_pointer != -1:
                    overflow_records = self._read_overflow(page.overflow_pointer)
                    for record in overflow_records:
                        results.append(self._record_to_dict(record))
            
            # Avanzar al siguiente nodo hoja
            if current_leaf.next_pointer != -1:
                current_leaf = self._read_node(current_leaf.next_pointer)
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
        for file_path in [self.data_file, self.tree_file, self.overflow_file]:
            with open(file_path, 'wb') as f:
                pass  # Truncar archivo
        
        # Resetear metadatos
        self.metadata = ISAMMetadata()
        self._save_metadata()
        
        # Limpiar cache
        self.node_cache.clear()
        
        print(f"✓ Índice limpiado: {count} registros eliminados")
        return count
    
    # ====================================================================
    #                    CIERRE Y DIAGNÓSTICO
    # ====================================================================
    
    def close(self):
        """Cierra el índice y persiste estado final"""
        self._save_metadata()
        self.node_cache.clear()
        print(f"\n{'='*60}")
        print(f"✓ ÍNDICE ISAM CERRADO")
        print(f"{'='*60}")
        print(f"Registros guardados: {self.metadata.num_records}")
        print(f"Niveles del árbol: {self.metadata.num_levels}")
        print(f"Nodos hoja: {self.metadata.num_leaf_nodes}")
        print(f"Páginas de datos: {self.metadata.num_pages}")
        print(f"{'='*60}\n")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas detalladas del índice.
        Útil para análisis de rendimiento.
        """
        # Calcular tamaño de archivos
        data_size = os.path.getsize(self.data_file) if os.path.exists(self.data_file) else 0
        tree_size = os.path.getsize(self.tree_file) if os.path.exists(self.tree_file) else 0
        overflow_size = os.path.getsize(self.overflow_file) if os.path.exists(self.overflow_file) else 0
        
        # Calcular registros en overflow
        num_overflow = overflow_size // self.record_size if self.record_size > 0 else 0
        
        return {
            'num_records': self.metadata.num_records,
            'num_levels': self.metadata.num_levels,
            'num_leaf_nodes': self.metadata.num_leaf_nodes,
            'num_pages': self.metadata.num_pages,
            'num_overflow_records': num_overflow,
            'data_file_size_kb': data_size / 1024,
            'tree_file_size_kb': tree_size / 1024,
            'overflow_file_size_kb': overflow_size / 1024,
            'total_size_kb': (data_size + tree_size + overflow_size) / 1024,
            'block_factor': self.block_factor,
            'record_size': self.record_size,
            'overflow_percentage': (num_overflow / self.metadata.num_records * 100) if self.metadata.num_records > 0 else 0
        }
    
    def print_statistics(self):
        """Imprime estadísticas del índice de forma legible"""
        stats = self.get_statistics()
        
        print(f"\n{'='*60}")
        print(f"ESTADÍSTICAS DEL ÍNDICE ISAM")
        print(f"{'='*60}")
        print(f"Estructura:")
        print(f"  - Niveles del árbol: {stats['num_levels']}")
        print(f"  - Nodos hoja (nivel 1): {stats['num_leaf_nodes']}")
        print(f"  - Páginas de datos (nivel 0): {stats['num_pages']}")
        print(f"  - Block factor: {stats['block_factor']}")
        print(f"\nRegistros:")
        print(f"  - Total de registros: {stats['num_records']}")
        print(f"  - Registros en páginas: {stats['num_records'] - stats['num_overflow_records']}")
        print(f"  - Registros en overflow: {stats['num_overflow_records']}")
        print(f"  - % en overflow: {stats['overflow_percentage']:.2f}%")
        print(f"\nAlmacenamiento:")
        print(f"  - Tamaño de registro: {stats['record_size']} bytes")
        print(f"  - Archivo de datos: {stats['data_file_size_kb']:.2f} KB")
        print(f"  - Archivo de árbol: {stats['tree_file_size_kb']:.2f} KB")
        print(f"  - Archivo de overflow: {stats['overflow_file_size_kb']:.2f} KB")
        print(f"  - TOTAL: {stats['total_size_kb']:.2f} KB")
        print(f"{'='*60}\n")
