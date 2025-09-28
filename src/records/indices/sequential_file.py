import os
import struct
from typing import List, Dict, Any, Optional, Tuple
from .base_index import BaseIndex
from ..record import DynamicRecord


class SequentialFileIndex(BaseIndex):
    def __init__(self, column_name: str, filename: str = None):
        super().__init__(column_name, filename)
        self.filename = filename or f"{column_name}_sequential.dat"
        self.aux_filename = f"{column_name}_aux.dat"
        self.records_cache = []
        self.is_loaded = False
        self.record_size = None
        self.max_aux_records = 10  # Número máximo de registros auxiliares antes de reorganizar
        
    def _ensure_loaded(self):
        if not self.is_loaded:
            self._load_records()
            self.is_loaded = True
    
    def _load_records(self):
        self.records_cache = []
        
        if os.path.exists(self.filename):
            with open(self.filename, 'rb') as f:
                while True:
                    try:
                        # Leer tamaño del registro
                        size_data = f.read(4)
                        if not size_data:
                            break
                        
                        record_size = struct.unpack('I', size_data)[0]
                        record_data = f.read(record_size)
                        
                        if len(record_data) != record_size:
                            break
                            
                        record_dict = self._deserialize_record(record_data)
                        if not record_dict.get('deleted', False):
                            self.records_cache.append(record_dict)
                            
                    except (struct.error, EOFError):
                        break
        
        if os.path.exists(self.aux_filename):
            with open(self.aux_filename, 'rb') as f:
                while True:
                    try:
                        size_data = f.read(4)
                        if not size_data:
                            break
                        
                        record_size = struct.unpack('I', size_data)[0]
                        record_data = f.read(record_size)
                        
                        if len(record_data) != record_size:
                            break
                            
                        record_dict = self._deserialize_record(record_data)
                        if not record_dict.get('deleted', False):
                            self.records_cache.append(record_dict)
                            
                    except (struct.error, EOFError):
                        break
        
        # Ordenar registros por la columna clave
        self.records_cache.sort(key=lambda x: self._get_sort_key(x[self.column_name]))
    
    def _get_sort_key(self, value):
        if isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            return value.lower()
        elif isinstance(value, list):
            return tuple(value) if value else ()
        else:
            return str(value)
    
    #Es como un pack, pero mas general
    def _serialize_record(self, record: Dict[str, Any]) -> bytes:
        import pickle
        return pickle.dumps(record)
    #Es el unpack
    def _deserialize_record(self, data: bytes) -> Dict[str, Any]:
        import pickle
        return pickle.loads(data)
    
    def _write_record_to_file(self, filename: str, record: Dict[str, Any]):
        record_data = self._serialize_record(record)
        with open(filename, 'ab') as f:
            f.write(struct.pack('I', len(record_data)))
            f.write(record_data)
    
    def _binary_search(self, target_key) -> int:
        self._ensure_loaded()
        
        left, right = 0, len(self.records_cache) - 1
        target_sort_key = self._get_sort_key(target_key)
        
        while left <= right:
            mid = (left + right) // 2
            mid_key = self._get_sort_key(self.records_cache[mid][self.column_name])
            
            if mid_key == target_sort_key:
                return mid
            elif mid_key < target_sort_key:
                left = mid + 1
            else:
                right = mid - 1
        
        return -1
    
    def _find_insertion_point(self, target_key) -> int:
        self._ensure_loaded()
        
        left, right = 0, len(self.records_cache)
        target_sort_key = self._get_sort_key(target_key)
        
        while left < right:
            mid = (left + right) // 2
            mid_key = self._get_sort_key(self.records_cache[mid][self.column_name])
            
            if mid_key < target_sort_key:
                left = mid + 1
            else:
                right = mid
        
        return left
    #A partir de aqui vienen las operaciones clasicas 
    def search(self, key: Any) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        
        index = self._binary_search(key)
        if index == -1:
            return []
        
        results = []
        target_sort_key = self._get_sort_key(key)
        
        i = index
        while i >= 0 and self._get_sort_key(self.records_cache[i][self.column_name]) == target_sort_key:
            results.append(self.records_cache[i].copy())
            i -= 1
        
        i = index + 1
        while i < len(self.records_cache) and self._get_sort_key(self.records_cache[i][self.column_name]) == target_sort_key:
            results.append(self.records_cache[i].copy())
            i += 1
        
        return results

    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        
        results = []
        begin_sort_key = self._get_sort_key(begin_key)
        end_sort_key = self._get_sort_key(end_key)
        
        for record in self.records_cache:
            record_key = self._get_sort_key(record[self.column_name])
            if begin_sort_key <= record_key <= end_sort_key:
                results.append(record.copy())
            elif record_key > end_sort_key:
                break 
        
        return results

    def add(self, record: Dict[str, Any]) -> bool:
        try:
            self._ensure_loaded()
            
            if self.column_name not in record:
                raise ValueError(f"El registro debe contener la columna '{self.column_name}'")
            
            self._write_record_to_file(self.aux_filename, record)
            
            insertion_point = self._find_insertion_point(record[self.column_name])
            self.records_cache.insert(insertion_point, record.copy())
            
            if self._count_aux_records() >= self.max_aux_records:
                self._reorganize_files()
            
            return True
            
        except Exception as e:
            print(f"Error añadiendo registro: {e}")
            return False
    
    def _count_aux_records(self) -> int:
        if not os.path.exists(self.aux_filename):
            return 0
        
        count = 0
        try:
            with open(self.aux_filename, 'rb') as f:
                while True:
                    size_data = f.read(4)
                    if not size_data:
                        break
                    
                    record_size = struct.unpack('I', size_data)[0]
                    f.seek(f.tell() + record_size)
                    count += 1
                    
        except (struct.error, EOFError):
            pass
            
        return count
    
    def _reorganize_files(self):
        try:
            temp_filename = f"{self.column_name}_temp.dat"
            
            with open(temp_filename, 'wb') as temp_file:
                for record in self.records_cache:
                    if not record.get('deleted', False):
                        record_data = self._serialize_record(record)
                        temp_file.write(struct.pack('I', len(record_data)))
                        temp_file.write(record_data)
            
            if os.path.exists(self.filename):
                os.remove(self.filename)
            os.rename(temp_filename, self.filename)
            
            if os.path.exists(self.aux_filename):
                os.remove(self.aux_filename)
                
        except Exception as e:
            print(f"Error reorganizando archivos: {e}")

    def remove(self, key: Any) -> bool:
        try:
            self._ensure_loaded()
            
            removed_count = 0
            target_sort_key = self._get_sort_key(key)
            
            i = 0
            while i < len(self.records_cache):
                record_key = self._get_sort_key(self.records_cache[i][self.column_name])
                if record_key == target_sort_key:
                    self.records_cache[i]['deleted'] = True
                    removed_count += 1
                i += 1
            
            self.records_cache = [r for r in self.records_cache if not r.get('deleted', False)]
            
            if removed_count > 0:
                self._reorganize_files()
            
            return removed_count > 0
            
        except Exception as e:
            print(f"Error eliminando registro: {e}")
            return False