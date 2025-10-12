from typing import List, Dict, Any, Optional, Union
import os
import struct
from .base_index import BaseIndex
from ..record import DynamicRecord
from ...parser.ast import ColumnDef

BLOCK_FACTOR = 4

class Page:
    HEADER_FORMAT = 'ii'  # size, next_page
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    SIZE_OF_PAGE = HEADER_SIZE + BLOCK_FACTOR * DynamicRecord.SIZE_OF_DynamicRecord

    def __init__(self, records=None, next_page=-1):
        self.records = records or []
        self.next_page = next_page

    def pack(self):
        header_data = struct.pack(self.HEADER_FORMAT, len(self.records), self.next_page)
        record_data = b''
        for record in self.records:
            record_data += record.pack()
        
        # Rellenar con registros vacíos si es necesario
        i = len(self.records)
        while i < BLOCK_FACTOR:
            record_data += b'\x00' * DynamicRecord.SIZE_OF_RECORD
            i += 1
        return header_data + record_data

    @staticmethod
    def unpack(data: bytes):
        size, next_page = struct.unpack(Page.HEADER_FORMAT, data[:Page.HEADER_SIZE])
        offset = Page.HEADER_SIZE
        records = []
        for i in range(size):
            record_data = data[offset: offset + DynamicRecord.SIZE_OF_RECORD]
            records.append(DynamicRecord.unpack(record_data))
            offset += DynamicRecord.SIZE_OF_RECORD
        return Page(records, next_page)

class Node:
    """Clase base para nodos del árbol ISAM"""
    def __init__(self, is_leaf=False):
        self.is_leaf = is_leaf

class ISAMIntermediateNode(Node):
    """Nodo intermedio del árbol ISAM con punteros a hijos"""
    # Formato: 3 valores (claves) y 4 punteros (3 hijos + 1 puntero extra)
    FORMAT = 'iii' + 'i' * 4  # 3 valores + 4 punteros
    SIZE = struct.calcsize(FORMAT)
    
    def __init__(self, values=None, pointers=None):
        super().__init__(is_leaf=False)
        self.values = values or [0, 0, 0]  # 3 valores/claves
        self.pointers = pointers or [-1, -1, -1, -1]  # 4 punteros a hijos
        
    def pack(self):
        values_data = struct.pack('iii', *self.values)
        pointers_data = struct.pack('iiii', *self.pointers)
        return values_data + pointers_data
    
    @staticmethod
    def unpack(data: bytes):
        if len(data) < ISAMIntermediateNode.SIZE:
            return ISAMIntermediateNode()
        
        values = struct.unpack('iii', data[:12])
        pointers = struct.unpack('iiii', data[12:28])
        return ISAMIntermediateNode(list(values), list(pointers))

class ISAMLeafNode(Node):
    """Nodo hoja del árbol ISAM con puntero a página de datos"""
    # Formato: valor de llave + puntero a página + puntero siguiente
    FORMAT = 'iii'  # key_value, data_page_pointer, next_pointer
    SIZE = struct.calcsize(FORMAT)
    
    def __init__(self, key_value=0, data_page_pointer=-1, next_pointer=-1):
        super().__init__(is_leaf=True)
        self.key_value = key_value
        self.data_page_pointer = data_page_pointer
        self.next_pointer = next_pointer
        
    def pack(self):
        return struct.pack(self.FORMAT, self.key_value, self.data_page_pointer, self.next_pointer)
    
    @staticmethod
    def unpack(data: bytes):
        if len(data) < ISAMLeafNode.SIZE:
            return ISAMLeafNode()
        key_value, data_page_pointer, next_pointer = struct.unpack(ISAMLeafNode.FORMAT, data)
        return ISAMLeafNode(key_value, data_page_pointer, next_pointer)

class ISAMIndex(BaseIndex):
    def __init__(self, column_name: str, table_schema: List[ColumnDef], filename: str = None, block_factor: int = 4):
        super().__init__(column_name, filename)
        self.table_schema = table_schema
        self.block_factor = block_factor
        
        temp_record = DynamicRecord._build_format(table_schema)
        self.record_size = struct.calcsize(temp_record)
        
        # Archivos
        self.data_file = filename or f"{column_name}_isam.dat"
        self.index_file = filename.replace('.dat', '_index.dat') if filename else f"{column_name}_index.dat"
        self.overflow_file = filename.replace('.dat', '_overflow.dat') if filename else f"{column_name}_overflow.dat"
        self.tree_file = filename.replace('.dat', '_tree.dat') if filename else f"{column_name}_tree.dat"
        
        self._ensure_files_exist()
        
        # Estructuras en memoria
        self.root_node = None
        self._load_tree_structure()
    
    def _ensure_files_exist(self):
        for file_path in [self.data_file, self.index_file, self.overflow_file, self.tree_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    pass
    
    def _load_tree_structure(self):
        """Carga la estructura del árbol desde archivo"""
        try:
            with open(self.tree_file, 'rb') as f:
                # Leer tipo de nodo raíz
                node_type = f.read(1)
                if node_type == b'I':  # Nodo intermedio
                    data = f.read(ISAMIntermediateNode.SIZE)
                    self.root_node = ISAMIntermediateNode.unpack(data)
                elif node_type == b'L':  # Nodo hoja
                    data = f.read(ISAMLeafNode.SIZE)
                    self.root_node = ISAMLeafNode.unpack(data)
        except:
            self.root_node = None
    
    def _save_tree_structure(self):
        """Guarda la estructura del árbol en archivo"""
        with open(self.tree_file, 'wb') as f:
            if isinstance(self.root_node, ISAMIntermediateNode):
                f.write(b'I')
                f.write(self.root_node.pack())
            elif isinstance(self.root_node, ISAMLeafNode):
                f.write(b'L')
                f.write(self.root_node.pack())
    
    def _read_page(self, position: int) -> Page:
        """Lee una página desde una posición específica"""
        with open(self.data_file, 'rb') as f:
            f.seek(position)
            data = f.read(Page.SIZE_OF_PAGE)
            return Page.unpack(data)
    
    def _write_page(self, page: Page) -> int:
        """Escribe una página y devuelve su posición"""
        with open(self.data_file, 'ab') as f:
            position = f.tell()
            f.write(page.pack())
        return position
    
    def _find_leaf_node(self, key: Any) -> Optional[ISAMLeafNode]:
        """Encuentra el nodo hoja correspondiente a una clave"""
        if not self.root_node:
            return None
        
        current = self.root_node
        
        # Navegar hasta el nodo hoja
        while not current.is_leaf:
            if isinstance(current, ISAMIntermediateNode):
                # Encontrar el puntero correcto basado en los valores
                if key < current.values[0]:
                    next_pointer = current.pointers[0]
                elif key < current.values[1]:
                    next_pointer = current.pointers[1]
                elif key < current.values[2]:
                    next_pointer = current.pointers[2]
                else:
                    next_pointer = current.pointers[3]
                
                if next_pointer == -1:
                    return None
                
                # Cargar el siguiente nodo (en implementación real leería del archivo)
                current = self._load_node_from_disk(next_pointer)
            else:
                break
        
        return current if current.is_leaf else None
    
    def _load_node_from_disk(self, pointer: int) -> Optional[Node]:
        """Carga un nodo desde disco basado en el puntero"""
        # Implementación simplificada - en realidad leería desde el archivo de árbol
        return None
    
    def build(self, records: List[Dict[str, Any]]):
        """Construye el índice ISAM completo"""
        if not records:
            return
        
        # Ordenar registros por clave
        records.sort(key=lambda r: r[self.column_name])
        
        # Crear páginas de datos
        pages = []
        for i in range(0, len(records), self.block_factor):
            page_records = records[i:i + self.block_factor]
            page = Page(page_records)
            pages.append(page)
        
        # Escribir páginas y crear nodos hoja
        leaf_nodes = []
        for i, page in enumerate(pages):
            position = self._write_page(page)
            key = page.records[0].get(self.column_name) if page.records else 0
            
            leaf_node = ISAMLeafNode(
                key_value=key,
                data_page_pointer=position,
                next_pointer=-1 if i == len(pages) - 1 else i + 1
            )
            leaf_nodes.append(leaf_node)
        
        # Construir árbol (simplificado - solo un nivel por ahora)
        if len(leaf_nodes) <= 4:
            # Caso simple: pocos nodos hoja, usar solo nodo intermedio
            self.root_node = ISAMIntermediateNode()
            for i, leaf in enumerate(leaf_nodes):
                if i < 3:
                    self.root_node.values[i] = leaf.key_value
                self.root_node.pointers[i] = i  # puntero al nodo hoja
        else:
            # Caso complejo: construir árbol multi-nivel (implementar recursivamente)
            pass
        
        self._save_tree_structure()
    
    def search(self, key: Any) -> List[Dict[str, Any]]:
        """Busca registros por clave usando el árbol ISAM"""
        leaf_node = self._find_leaf_node(key)
        if not leaf_node:
            return []
        
        # Leer la página de datos
        page = self._read_page(leaf_node.data_page_pointer)
        
        # Filtrar registros por clave
        results = []
        for record in page.records:
            if record.get(self.column_name) == key:
                results.append(record.to_dict())
        
        return results
    
    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        """Búsqueda por rango de claves"""
        results = []
        current_leaf = self._find_leaf_node(begin_key)
        
        while current_leaf:
            page = self._read_page(current_leaf.data_page_pointer)
            
            for record in page.records:
                key_val = record.get(self.column_name)
                if begin_key <= key_val <= end_key:
                    results.append(record.to_dict())
                elif key_val > end_key:
                    return results
            
            # Mover al siguiente nodo hoja
            if current_leaf.next_pointer != -1:
                current_leaf = self._load_node_from_disk(current_leaf.next_pointer)
            else:
                break
        
        return results
    
    def add(self, record: Dict[str, Any]) -> bool:
        """Añade un nuevo registro"""
        key = record[self.column_name]
        leaf_node = self._find_leaf_node(key)
        
        if not leaf_node:
            return False
        
        # Leer página actual
        page = self._read_page(leaf_node.data_page_pointer)
        
        if len(page.records) < self.block_factor:
            # Hay espacio en la página
            page.records.append(DynamicRecord(self.table_schema, **record))
            page.records.sort(key=lambda r: r.get(self.column_name))
            
            # Reescribir página
            with open(self.data_file, 'r+b') as f:
                f.seek(leaf_node.data_page_pointer)
                f.write(page.pack())
            return True
        else:
            # Página llena - escribir en overflow
            with open(self.overflow_file, 'ab') as f:
                rec = DynamicRecord(self.table_schema, **record)
                f.write(rec.pack())
            return True
    
    def remove(self, key: Any) -> bool:
        """Elimina registros por clave"""
        leaf_node = self._find_leaf_node(key)
        if not leaf_node:
            return False
        
        page = self._read_page(leaf_node.data_page_pointer)
        original_count = len(page.records)
        
        # Filtrar registros
        page.records = [r for r in page.records if r.get(self.column_name) != key]
        
        if len(page.records) < original_count:
            # Reescribir página
            with open(self.data_file, 'r+b') as f:
                f.seek(leaf_node.data_page_pointer)
                f.write(page.pack())
            return True
        
        return False