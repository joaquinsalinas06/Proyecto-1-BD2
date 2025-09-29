import os
import struct
import ast
from typing import List, Dict, Any
from .base_index import BaseIndex


class SequentialFileIndex(BaseIndex):    
    def __init__(self, column_name: str, filename: str = None):
        super().__init__(column_name, filename)
        self.filename = filename or f"{column_name}_sequential.dat"
        self.aux_filename = f"{column_name}_aux.dat"
        self.free_list_filename = f"{column_name}_freelist.dat"
        self.max_aux_records = 5
        
        self.free_positions = self._load_free_list()
    
    def _load_free_list(self) -> List[int]:
        if not os.path.exists(self.free_list_filename):
            return []
        
        free_positions = []
        with open(self.free_list_filename, 'rb') as f:
            while True:
                pos_data = f.read(8)
                if len(pos_data) != 8:
                    break
                position = struct.unpack('Q', pos_data)[0]
                free_positions.append(position)
        return free_positions
    
    def _save_free_list(self):
        with open(self.free_list_filename, 'wb') as f:
            for position in self.free_positions:
                f.write(struct.pack('Q', position))
    
    def _record_to_bytes(self, record: Dict[str, Any], deleted: bool = False) -> bytes:
        key_value = record[self.column_name]
        
        if isinstance(key_value, int):
            key_bytes = struct.pack('i', key_value)
        elif isinstance(key_value, float):
            key_bytes = struct.pack('f', key_value)
        elif isinstance(key_value, str):
            key_str = key_value.encode('utf-8')
            key_bytes = struct.pack('I', len(key_str)) + key_str
        else:
            key_str = str(key_value).encode('utf-8')
            key_bytes = struct.pack('I', len(key_str)) + key_str
        
        data_str = str(record).encode('utf-8')
        
        deleted_flag = b'\x01' if deleted else b'\x00'
        return deleted_flag + struct.pack('I', len(key_bytes)) + key_bytes + struct.pack('I', len(data_str)) + data_str
    
    def _bytes_to_record(self, data: bytes) -> tuple[Dict[str, Any], bool]:
        offset = 0
        
        deleted_flag = data[offset:offset+1]
        is_deleted = deleted_flag == b'\x01'
        offset += 1
        
        key_size = struct.unpack('I', data[offset:offset+4])[0]
        offset += 4
        
        offset += key_size
        
        data_size = struct.unpack('I', data[offset:offset+4])[0]
        offset += 4
        
        record_str = data[offset:offset+data_size].decode('utf-8')
        record = ast.literal_eval(record_str)
        return record, is_deleted
    
    def _read_all_records(self) -> List[Dict[str, Any]]:
        records = []
        
        if os.path.exists(self.filename):
            with open(self.filename, 'rb') as f:
                while True:
                    size_data = f.read(4)
                    if len(size_data) != 4:
                        break
                    
                    record_size = struct.unpack('I', size_data)[0]
                    record_data = f.read(record_size)
                    
                    if len(record_data) != record_size:
                        break
                    
                    record, is_deleted = self._bytes_to_record(record_data)
                    if not is_deleted:
                        records.append(record)
        
        if os.path.exists(self.aux_filename):
            with open(self.aux_filename, 'rb') as f:
                while True:
                    size_data = f.read(4)
                    if len(size_data) != 4:
                        break
                    
                    record_size = struct.unpack('I', size_data)[0]
                    record_data = f.read(record_size)
                    
                    if len(record_data) != record_size:
                        break
                    
                    record, is_deleted = self._bytes_to_record(record_data)
                    if not is_deleted:
                        records.append(record)
        
        records.sort(key=lambda x: x[self.column_name])
        return records
    
    def _write_record(self, filename: str, record: Dict[str, Any], deleted: bool = False):
        record_bytes = self._record_to_bytes(record, deleted)
        with open(filename, 'ab') as f:
            f.write(struct.pack('I', len(record_bytes)))
            f.write(record_bytes)
    
    def _write_record_at_position(self, filename: str, position: int, record: Dict[str, Any]):
        record_bytes = self._record_to_bytes(record, deleted=False)
        with open(filename, 'r+b') as f:
            f.seek(position)
            current_size_data = f.read(4)
            if len(current_size_data) == 4:
                current_size = struct.unpack('I', current_size_data)[0]
                new_size = len(record_bytes)
                
                if new_size <= current_size:
                    f.seek(position)
                    f.write(struct.pack('I', new_size))
                    f.write(record_bytes)
                    remaining = current_size - new_size
                    if remaining > 0:
                        f.write(b'\x00' * remaining)
                else:
                    f.seek(position + 1)
                    f.write(b'\x01')
                    self.free_positions.append(position)
                    self._write_record(self.aux_filename, record)
    
    def search(self, key: Any) -> List[Dict[str, Any]]:
        records = self._read_all_records()
        results = []
        
        left, right = 0, len(records) - 1
        found_index = -1
        
        while left <= right:
            mid = (left + right) // 2
            mid_key = records[mid][self.column_name]
            
            if mid_key == key:
                found_index = mid
                break
            elif mid_key < key:
                left = mid + 1
            else:
                right = mid - 1
        
        if found_index != -1:
            i = found_index
            while i >= 0 and records[i][self.column_name] == key:
                results.append(records[i])
                i -= 1
            
            i = found_index + 1
            while i < len(records) and records[i][self.column_name] == key:
                results.append(records[i])
                i += 1
        
        return results

    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        records = self._read_all_records()
        results = []
        
        left, right = 0, len(records) - 1
        start_index = len(records)
        while left <= right:
            mid = (left + right) // 2
            mid_key = records[mid][self.column_name]
            if mid_key < begin_key:
                left = mid + 1
            else:
                start_index = mid
                right = mid - 1
        
        i = start_index
        while i < len(records):
            record_key = records[i][self.column_name]
            if record_key > end_key:
                break
            if begin_key <= record_key <= end_key:
                results.append(records[i])
            i += 1
        
        return results

    def add(self, record: Dict[str, Any]) -> bool:
        if self.column_name not in record:
            return False
        
        if self.free_positions:
            position = self.free_positions.pop(0)
            self._write_record_at_position(self.filename, position, record)
            self._save_free_list()
        else:
            self._write_record(self.aux_filename, record)
        
        if not self.free_positions:
            count = 0
            if os.path.exists(self.aux_filename):
                file_size = os.path.getsize(self.aux_filename)
                if file_size < 1000:
                    with open(self.aux_filename, 'rb') as f:
                        while True:
                            size_data = f.read(4)
                            if len(size_data) != 4:
                                break
                            record_size = struct.unpack('I', size_data)[0]
                            f.seek(f.tell() + record_size)
                            count += 1
                else:
                    count = file_size // 50
            
            if count >= self.max_aux_records:
                all_records = self._read_all_records()
                
                if os.path.exists(self.filename):
                    os.remove(self.filename)
                if os.path.exists(self.aux_filename):
                    os.remove(self.aux_filename)
                
                for rec in all_records:
                    self._write_record(self.filename, rec)
                
                self.free_positions = []
                self._save_free_list()
        
        return True

    def remove(self, key: Any) -> bool:
        found = False
        
        if os.path.exists(self.filename):
            found = self._mark_deleted_in_file(self.filename, key) or found
            
        if os.path.exists(self.aux_filename):
            found = self._mark_deleted_in_file(self.aux_filename, key) or found
        
        if found:
            self._save_free_list()
        
        return found
    
    def _mark_deleted_in_file(self, filename: str, key: Any) -> bool:
        found = False
        
        with open(filename, 'r+b') as f:
            while True:
                position = f.tell()
                size_data = f.read(4)
                if len(size_data) != 4:
                    break
                
                record_size = struct.unpack('I', size_data)[0]
                record_data = f.read(record_size)
                
                if len(record_data) != record_size:
                    break
                
                record, is_deleted = self._bytes_to_record(record_data)
                
                if not is_deleted and record[self.column_name] == key:
                    f.seek(position + 4 + 1)
                    f.write(b'\x01')
                    
                    self.free_positions.append(position)
                    found = True
        
        return found