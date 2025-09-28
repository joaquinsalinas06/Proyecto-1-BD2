import os
import struct
from typing import List, Dict, Any
from .base_index import BaseIndex


class SequentialFileIndex(BaseIndex):    
    def __init__(self, column_name: str, filename: str = None):
        super().__init__(column_name, filename)
        self.filename = filename or f"{column_name}_sequential.dat"
        self.aux_filename = f"{column_name}_aux.dat"
        self.max_aux_records = 5
    
    def _record_to_bytes(self, record: Dict[str, Any]) -> bytes:
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
        
        return struct.pack('I', len(key_bytes)) + key_bytes + struct.pack('I', len(data_str)) + data_str
    
    def _bytes_to_record(self, data: bytes) -> Dict[str, Any]:
        offset = 0
        
        key_size = struct.unpack('I', data[offset:offset+4])[0]
        offset += 4
        
        offset += key_size
        
        data_size = struct.unpack('I', data[offset:offset+4])[0]
        offset += 4
        
        record_str = data[offset:offset+data_size].decode('utf-8')
        return eval(record_str)
    
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
                    
                    record = self._bytes_to_record(record_data)
                    if not record.get('deleted', False):
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
                    
                    record = self._bytes_to_record(record_data)
                    if not record.get('deleted', False):
                        records.append(record)
        
        records.sort(key=lambda x: x[self.column_name])
        return records
    
    def _write_record(self, filename: str, record: Dict[str, Any]):
        record_bytes = self._record_to_bytes(record)
        with open(filename, 'ab') as f:
            f.write(struct.pack('I', len(record_bytes)))
            f.write(record_bytes)
    
    def search(self, key: Any) -> List[Dict[str, Any]]:
        records = self._read_all_records()
        results = []
        
        #binary search
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
        
        for record in records:
            record_key = record[self.column_name]
            if begin_key <= record_key <= end_key:
                results.append(record)
        
        return results

    def add(self, record: Dict[str, Any]) -> bool:
        if self.column_name not in record:
            return False
        
        self._write_record(self.aux_filename, record)
        
        count = 0
        if os.path.exists(self.aux_filename):
            with open(self.aux_filename, 'rb') as f:
                while True:
                    size_data = f.read(4)
                    if len(size_data) != 4:
                        break
                    record_size = struct.unpack('I', size_data)[0]
                    f.seek(f.tell() + record_size)
                    count += 1
        
        if count >= self.max_aux_records:
            all_records = self._read_all_records()
            
            if os.path.exists(self.filename):
                os.remove(self.filename)
            if os.path.exists(self.aux_filename):
                os.remove(self.aux_filename)
            
            for rec in all_records:
                self._write_record(self.filename, rec)
        
        return True

    def remove(self, key: Any) -> bool:
        records = self._read_all_records()
        found = False
        
        for record in records:
            if record[self.column_name] == key:
                record['deleted'] = True
                found = True
        
        if found:
            if os.path.exists(self.filename):
                os.remove(self.filename)
            if os.path.exists(self.aux_filename):
                os.remove(self.aux_filename)
            
            for record in records:
                if not record.get('deleted', False):
                    self._write_record(self.filename, record)
        
        return found