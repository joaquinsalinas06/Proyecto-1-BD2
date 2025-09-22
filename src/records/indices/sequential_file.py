import os
import struct
from typing import List, Dict, Any, Optional, Tuple
from .base_index import BaseIndex
from ..record import DynamicRecord


class SequentialFileRecord:
    BINARY_FORMAT = '<i100sib'
    FIXED_SIZE = struct.calcsize(BINARY_FORMAT)
    MAX_DATA_LENGTH = 100
    
    def __init__(self, key: int, data: str, next_pos: int = -1, deleted: bool = False):
        if key < 0:
            raise ValueError("La clave debe ser >= 0")
        
        self.key = key
        self.next_pos = next_pos
        self.deleted = bool(deleted)
        self._set_data(data)
    
    def _set_data(self, data: str):
        if not isinstance(data, str):
            data = str(data)
        
        if len(data) > self.MAX_DATA_LENGTH:
            data = data[:self.MAX_DATA_LENGTH]
        
        data_bytes = data.encode('utf-8')[:self.MAX_DATA_LENGTH]
        self.data = data_bytes.decode('utf-8', errors='ignore').ljust(self.MAX_DATA_LENGTH, '\0')
    
    def serialize(self) -> bytes:
        data_bytes = self.data.encode('utf-8')[:self.MAX_DATA_LENGTH]
        data_bytes = data_bytes.ljust(self.MAX_DATA_LENGTH, b'\0')
        
        return struct.pack(
            self.BINARY_FORMAT,
            self.key,
            data_bytes,
            self.next_pos,
            1 if self.deleted else 0
        )
    
    @classmethod
    def deserialize(cls, binary_data: bytes) -> 'SequentialFileRecord':
        if len(binary_data) != cls.FIXED_SIZE:
            raise ValueError(f"Datos binarios inválidos. Esperado: {cls.FIXED_SIZE} bytes, recibido: {len(binary_data)}")
        
        key, data_bytes, next_pos, deleted_int = struct.unpack(cls.BINARY_FORMAT, binary_data)
        
        data_str = data_bytes.decode('utf-8', errors='ignore').rstrip('\0')
        deleted = bool(deleted_int)
        
        return cls(key, data_str, next_pos, deleted)
    
    @staticmethod
    def size() -> int:
        return SequentialFileRecord.FIXED_SIZE
    
    def is_valid(self) -> bool:
        return (
            isinstance(self.key, int) and 
            self.key >= 0 and
            isinstance(self.next_pos, int) and
            isinstance(self.deleted, bool)
        )
    
    def __str__(self) -> str:
        status = "DELETED" if self.deleted else "ACTIVE"
        return f"SequentialFileRecord(key={self.key}, data='{self.data.strip()}', next={self.next_pos}, status={status})"


class SequentialFileIndex(BaseIndex):
    def __init__(self, column_name: str, filename: str = None, k: int = 10):
        super().__init__(column_name, filename)
        self.k = k
        self.main_filename = f"{self.filename}_main.dat"
        self.aux_filename = f"{self.filename}_aux.dat"
        self.record_size = SequentialFileRecord.size()
        self._initialize_files()
    
    def _initialize_files(self):
        for filename in [self.main_filename, self.aux_filename]:
            if not os.path.exists(filename):
                with open(filename, 'wb') as f:
                    pass

    def search(self, key: Any) -> List[Dict[str, Any]]:
        # Convertir clave
        if isinstance(key, int) and key >= 0:
            search_key = key
        elif isinstance(key, str) and key.isdigit():
            search_key = int(key)
        else:
            search_key = hash(str(key)) % (2**31) if key else 0
        
        if search_key < 0:
            return []
        
        if os.path.exists(self.main_filename):
            left = 0
            right = (os.path.getsize(self.main_filename) // self.record_size) - 1
            
            while left <= right:
                mid = (left + right) // 2
                with open(self.main_filename, 'rb') as f:
                    f.seek(mid * self.record_size)
                    data = f.read(self.record_size)
                    if len(data) == self.record_size:
                        record = SequentialFileRecord.deserialize(data)
                        if record.key == search_key and not record.deleted:
                            return [{
                                self.column_name: record.key,
                                '_data': record.data.strip('\0'),
                                '_deleted': record.deleted
                            }]
                        elif record.key < search_key:
                            left = mid + 1
                        else:
                            right = mid - 1
                    else:
                        break
        
        if os.path.exists(self.aux_filename):
            aux_size = os.path.getsize(self.aux_filename) // self.record_size
            with open(self.aux_filename, 'rb') as f:
                for i in range(aux_size):
                    f.seek(i * self.record_size)
                    data = f.read(self.record_size)
                    if len(data) == self.record_size:
                        record = SequentialFileRecord.deserialize(data)
                        if record.key == search_key and not record.deleted:
                            return [{
                                self.column_name: record.key,
                                '_data': record.data.strip('\0'),
                                '_deleted': record.deleted
                            }]
        
        return []

    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        if isinstance(begin_key, int) and begin_key >= 0:
            min_key = begin_key
        elif isinstance(begin_key, str) and begin_key.isdigit():
            min_key = int(begin_key)
        else:
            min_key = hash(str(begin_key)) % (2**31) if begin_key else 0
            
        if isinstance(end_key, int) and end_key >= 0:
            max_key = end_key
        elif isinstance(end_key, str) and end_key.isdigit():
            max_key = int(end_key)
        else:
            max_key = hash(str(end_key)) % (2**31) if end_key else 0
        
        if min_key < 0 or max_key < 0 or min_key > max_key:
            return []
        
        result = []
        seen_keys = set()
        
        if os.path.exists(self.main_filename):
            main_size = os.path.getsize(self.main_filename) // self.record_size
            with open(self.main_filename, 'rb') as f:
                for i in range(main_size):
                    f.seek(i * self.record_size)
                    data = f.read(self.record_size)
                    if len(data) == self.record_size:
                        record = SequentialFileRecord.deserialize(data)
                        if min_key <= record.key <= max_key and not record.deleted:
                            if record.key not in seen_keys:
                                result.append({
                                    self.column_name: record.key,
                                    '_data': record.data.strip('\0'),
                                    '_deleted': record.deleted
                                })
                                seen_keys.add(record.key)
        
        if os.path.exists(self.aux_filename):
            aux_size = os.path.getsize(self.aux_filename) // self.record_size
            with open(self.aux_filename, 'rb') as f:
                for i in range(aux_size):
                    f.seek(i * self.record_size)
                    data = f.read(self.record_size)
                    if len(data) == self.record_size:
                        record = SequentialFileRecord.deserialize(data)
                        if min_key <= record.key <= max_key and not record.deleted:
                            if record.key not in seen_keys:
                                result.append({
                                    self.column_name: record.key,
                                    '_data': record.data.strip('\0'),
                                    '_deleted': record.deleted
                                })
                                seen_keys.add(record.key)
        
        result.sort(key=lambda r: r[self.column_name])
        return result

    def add(self, record: Dict[str, Any]) -> bool:
        key_value = record.get(self.column_name)
        if key_value is None:
            return False
        
        if isinstance(key_value, int) and key_value >= 0:
            key = key_value
        elif isinstance(key_value, str) and key_value.isdigit():
            key = int(key_value)
        else:
            key = hash(str(key_value)) % (2**31) if key_value else 0
        
        if self.search(key):
            return False
        
        data_str = str(record)[:SequentialFileRecord.MAX_DATA_LENGTH]
        seq_record = SequentialFileRecord(key, data_str)
        
        aux_size = os.path.getsize(self.aux_filename) // self.record_size if os.path.exists(self.aux_filename) else 0
        
        with open(self.aux_filename, 'ab') as f:
            f.write(seq_record.serialize())
        
        if aux_size + 1 >= self.k:
            all_records = []
            
            if os.path.exists(self.main_filename):
                main_size = os.path.getsize(self.main_filename) // self.record_size
                with open(self.main_filename, 'rb') as f:
                    for i in range(main_size):
                        f.seek(i * self.record_size)
                        data = f.read(self.record_size)
                        if len(data) == self.record_size:
                            r = SequentialFileRecord.deserialize(data)
                            if not r.deleted:
                                all_records.append(r)
            
            aux_size = os.path.getsize(self.aux_filename) // self.record_size
            with open(self.aux_filename, 'rb') as f:
                for i in range(aux_size):
                    f.seek(i * self.record_size)
                    data = f.read(self.record_size)
                    if len(data) == self.record_size:
                        r = SequentialFileRecord.deserialize(data)
                        if not r.deleted:
                            all_records.append(r)
            
            all_records.sort(key=lambda r: r.key)
            for i in range(len(all_records)):
                all_records[i].next_pos = i + 1 if i < len(all_records) - 1 else -1
            
            with open(self.main_filename, 'wb') as f:
                for r in all_records:
                    f.write(r.serialize())
            
            with open(self.aux_filename, 'wb') as f:
                pass
        
        return True

    def remove(self, key: Any) -> bool:
        if isinstance(key, int) and key >= 0:
            search_key = key
        elif isinstance(key, str) and key.isdigit():
            search_key = int(key)
        else:
            search_key = hash(str(key)) % (2**31) if key else 0
        
        if search_key < 0:
            return False
        
        if os.path.exists(self.main_filename):
            main_size = os.path.getsize(self.main_filename) // self.record_size
            for i in range(main_size):
                with open(self.main_filename, 'r+b') as f:
                    f.seek(i * self.record_size)
                    data = f.read(self.record_size)
                    if len(data) == self.record_size:
                        record = SequentialFileRecord.deserialize(data)
                        if record.key == search_key and not record.deleted:
                            record.deleted = True
                            f.seek(i * self.record_size)
                            f.write(record.serialize())
                            return True
        
        if os.path.exists(self.aux_filename):
            aux_size = os.path.getsize(self.aux_filename) // self.record_size
            for i in range(aux_size):
                with open(self.aux_filename, 'r+b') as f:
                    f.seek(i * self.record_size)
                    data = f.read(self.record_size)
                    if len(data) == self.record_size:
                        record = SequentialFileRecord.deserialize(data)
                        if record.key == search_key and not record.deleted:
                            record.deleted = True
                            f.seek(i * self.record_size)
                            f.write(record.serialize())
                            return True
        
        return False