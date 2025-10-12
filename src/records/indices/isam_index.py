from typing import List, Dict, Any

import os
import struct
from typing import List, Dict, Any, Optional
from .base_index import BaseIndex
from ..record import DynamicRecord
from ...parser.ast import ColumnDef

#preguntar sobre table schema
class ISAMIndex(BaseIndex):
    def __init__(self, column_name: str, table_schema: List[ColumnDef], filename: str = None, block_factor: int = 4):
        super().__init__(column_name, filename)
        self.table_schema = table_schema
        self.block_factor = block_factor
        
        temp_record = DynamicRecord._build_format(table_schema)
        self.record_size = struct.calcsize(temp_record)
        
        # Archivos
        self.data_file = filename or f"{column_name}_isam.dat"
        self.index_file = filename.replace('.dat', '_index.dat') if isinstance(filename, str) else f"{column_name}_index.dat"
        self.overflow_file = filename.replace('.dat', '_overflow.dat') if isinstance(filename, str) else f"{column_name}_overflow.dat"
        
        self._ensure_files_exist()
        
        # Estructura de índice en memoria
        self.primary_index = self._load_index()
    
    def _ensure_files_exist(self):
        for file_path in [self.data_file, self.index_file, self.overflow_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    pass
    
    def _load_index(self) -> List[Dict[str, Any]]:
        """Carga el índice primario en memoria"""
        index = []
        if not os.path.exists(self.index_file):
            return index
        
        with open(self.index_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 2:
                    key, pos = parts
                    index.append({"key": key, "pos": int(pos)})
        return index
    
    def _save_index(self):
        with open(self.index_file, 'w') as f:
            for entry in self.primary_index:
                f.write(f"{entry['key']},{entry['pos']}\n")
    
    # --------------------------- Utilidades --------------------------- #
    
    def _read_block(self, position: int) -> List[Dict[str, Any]]:
        """Lee un bloque de registros desde una posición en el archivo principal"""
        records = []
        with open(self.data_file, 'rb') as f:
            f.seek(position)
            for _ in range(self.block_factor):
                data = f.read(self.record_size)
                if len(data) < self.record_size:
                    break
                record = DynamicRecord.unpack(self.table_schema, data)
                records.append(record.to_dict())
        return records
    
    def _write_block(self, records: List[Dict[str, Any]]) -> int:
        """Escribe un bloque y devuelve el offset inicial"""
        with open(self.data_file, 'ab') as f:
            pos = f.tell()
            for record_data in records:
                record = DynamicRecord(self.table_schema, **record_data)
                f.write(record.pack())
        return pos
    
    # --------------------------- Construcción inicial --------------------------- #
    
    def build(self, records: List[Dict[str, Any]]):
        """Construye el archivo ISAM ordenado y su índice primario"""
        if not records:
            return
        
        records.sort(key=lambda r: r[self.column_name])
        
        blocks = [records[i:i+self.block_factor] for i in range(0, len(records), self.block_factor)]
        
        self.primary_index.clear()
        with open(self.data_file, 'wb') as f:
            pass
        
        for block in blocks:
            pos = self._write_block(block)
            key = block[0][self.column_name]
            self.primary_index.append({"key": key, "pos": pos})
        
        self._save_index()
    
    # --------------------------- Búsqueda --------------------------- #
    
    def search(self, key: Any) -> List[Dict[str, Any]]:
        """Busca registros usando el índice primario"""
        if not self.primary_index:
            return []
        
        # Buscar el bloque adecuado
        target_block = None
        for i, entry in enumerate(self.primary_index):
            if key < entry['key']:
                if i == 0:
                    target_block = self.primary_index[0]
                else:
                    target_block = self.primary_index[i-1]
                break
        if target_block is None:
            target_block = self.primary_index[-1]
        
        # Leer el bloque
        block_records = self._read_block(target_block['pos'])
        
        # Filtrar por clave
        result = [r for r in block_records if r[self.column_name] == key]
        return result
    
    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        results = []
        for entry in self.primary_index:
            block = self._read_block(entry['pos'])
            for r in block:
                key_val = r[self.column_name]
                if begin_key <= key_val <= end_key:
                    results.append(r)
        return results
    
    # --------------------------- Inserción --------------------------- #
    
    def add(self, record: Dict[str, Any]) -> bool:
        key = record[self.column_name]
        if not self.primary_index:
            pos = self._write_block([record])
            self.primary_index.append({"key": key, "pos": pos})
            self._save_index()
            return True
        
        # Buscar bloque donde debería ir
        target_block = None
        for i, entry in enumerate(self.primary_index):
            if key < entry['key']:
                target_block = self.primary_index[i-1] if i > 0 else self.primary_index[0]
                break
        if target_block is None:
            target_block = self.primary_index[-1]
        
        # Leer bloque y ver si hay espacio
        block_records = self._read_block(target_block['pos'])
        if len(block_records) < self.block_factor:
            block_records.append(record)
            block_records.sort(key=lambda r: r[self.column_name])
            
            # Reescribir bloque
            with open(self.data_file, 'r+b') as f:
                f.seek(target_block['pos'])
                for r in block_records:
                    rec = DynamicRecord(self.table_schema, **r)
                    f.write(rec.pack())
            return True
        else:
            # Escribir en overflow
            with open(self.overflow_file, 'ab') as f:
                rec = DynamicRecord(self.table_schema, **record)
                f.write(rec.pack())
            return True
    
    # --------------------------- Eliminación --------------------------- #
    
    def remove(self, key: Any) -> bool:
        """Elimina registro si existe (solo en bloque principal, no en overflow para simplificar)"""
        for entry in self.primary_index:
            block_records = self._read_block(entry['pos'])
            filtered = [r for r in block_records if r[self.column_name] != key]
            if len(filtered) != len(block_records):
                # Reescribir bloque sin ese registro
                with open(self.data_file, 'r+b') as f:
                    f.seek(entry['pos'])
                    for r in filtered:
                        rec = DynamicRecord(self.table_schema, **r)
                        f.write(rec.pack())
                return True
        return False
