import os
import struct
import math
from typing import List, Dict, Any, Optional
from .base_index import BaseIndex
from ..record import DynamicRecord
from ...parser.ast import ColumnDef


class SequentialFileIndex(BaseIndex):
    def __init__(self, column_name: str, table_schema: List[ColumnDef], filename: str = None, is_primary: bool = False, primary_key_column: str = None, max_auxiliary_records: int = None):
        super().__init__(column_name, filename, is_primary, primary_key_column)
        self.table_schema = table_schema
        self._fixed_max_aux = max_auxiliary_records
        
        self._min_bound = None
        self._max_bound = None
        
        self.io_stats = {
            'disk_reads': 0,
            'disk_writes': 0,
        }
        
        temp_record = DynamicRecord._build_format(table_schema)
        self.record_size = struct.calcsize(temp_record)
        
        if filename:
            if not filename.endswith('.dat'):
                filename = filename + '.dat'
            self.main_file = filename
            self.aux_file = filename.replace('.dat', '_aux.dat')
        else:
            self.main_file = f"{column_name}_main.dat"
            self.aux_file = f"{column_name}_aux.dat"
        
        self._ensure_files_exist()
        
        self._main_record_count = self._initialize_main_count()
    
    def _ensure_files_exist(self):
        for file_path in [self.main_file, self.aux_file]:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    pass
    
    def _initialize_main_count(self) -> int:
        if not os.path.exists(self.main_file):
            return 0

        file_size = os.path.getsize(self.main_file)
        count = file_size // self.record_size

        self._update_bounds()

        return count

    def calcular_Aux(self) -> int:
        if self._fixed_max_aux is not None:
            return self._fixed_max_aux

        total_records = self._main_record_count + self._get_aux_count()

        if total_records == 0:
            return 5
        
        max_aux = max(2, int(math.log2(total_records)))
        return max_aux
    
    def reset_io_stats(self):
        """Resetear contadores de I/O"""
        self.io_stats = {
            'disk_reads': 0,
            'disk_writes': 0,
        }
    
    def get_io_stats(self) -> Dict[str, int]:
        """Obtener estadísticas de I/O actuales"""
        return self.io_stats.copy()
        
    def _update_bounds(self):
        records = self._read_records_from_file(self.main_file)
        if records:
            values = [r[self.column_name] for r in records]
            self._min_bound = min(values)
            self._max_bound = max(values)
        else:
            self._min_bound = None
            self._max_bound = None
    
    def _write_record_to_file(self, file_path: str, record_data: Dict[str, Any]) -> bool:
        record = DynamicRecord(self.table_schema, **record_data)
        packed_data = record.pack()
        
        self.io_stats['disk_writes'] += 1
        with open(file_path, 'ab') as f:
            f.write(packed_data)
        return True
    
    def _read_records_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        records = []
        if not os.path.exists(file_path):
            return records


        f = None
        try:
            f = open(file_path, 'rb')
            while True:
                data = f.read(self.record_size)
                if len(data) < self.record_size:
                    break

                self.io_stats['disk_reads'] += 1 
                try:
                    record = DynamicRecord.unpack(self.table_schema, data)
                    if not record.deleted:
                        record_dict = {}
                        for col in self.table_schema:
                            record_dict[col.name] = getattr(record, col.name)
                        records.append(record_dict)
                except (UnicodeDecodeError, struct.error):
                    # Skip corrupted records
                    continue
        finally:
            if f is not None:
                f.close()

        return records
    
    def _write_all_records_to_file(self, file_path: str, records: List[Dict[str, Any]]) -> bool:
        with open(file_path, 'wb') as f:
            for _, record_data in enumerate(records):
                self.io_stats['disk_writes'] += 1  # Count each record write
                record = DynamicRecord(self.table_schema, **record_data)
                packed_data = record.pack()
                f.write(packed_data)
        return True
    
    def _get_aux_count(self) -> int:
        if not os.path.exists(self.aux_file):
            return 0
        
        file_size = os.path.getsize(self.aux_file)
        return file_size // self.record_size
    
    def getAllRecords(self) -> List[Dict[str, Any]]:
        all_records = []
        
        main_records = self._read_records_from_file(self.main_file)
        all_records.extend(main_records)
        
        aux_records = self._read_records_from_file(self.aux_file)
        all_records.extend(aux_records)
        
        return all_records
    
    def clear_all(self) -> int:

        count = self._main_record_count + self._get_aux_count()

        self.io_stats['disk_writes'] += 2  
        with open(self.main_file, 'wb') as f:
            pass
        
        with open(self.aux_file, 'wb') as f:
            pass
        
        self._main_record_count = 0
        
        return count
        
    def search(self, key: Any) -> List[Dict[str, Any]]:
        results = []
        if os.path.exists(self.main_file):
            total_records = self._main_record_count
            if total_records > 0:
                left, right = 0, total_records - 1
                found_position = -1
                
                while left <= right:
                    mid = (left + right) // 2
                    mid_record = self._read_record_at_position(self.main_file, mid)
                    
                    if mid_record is None:
                        break
                    
                    mid_key = mid_record[self.column_name]
                    
                    if mid_key == key:
                        found_position = mid
                        break
                    elif mid_key < key:
                        left = mid + 1
                    else:
                        right = mid - 1
                
                if found_position != -1:
                    found_record = self._read_record_at_position(self.main_file, found_position)
                    if found_record:
                        results.append(found_record)
                    pos = found_position - 1
                    while pos >= 0:
                        record = self._read_record_at_position(self.main_file, pos)
                        if record and record[self.column_name] == key:
                            results.insert(0, record)
                            pos -= 1
                        else:
                            break
                    
                    pos = found_position + 1
                    while pos < total_records:
                        record = self._read_record_at_position(self.main_file, pos)
                        if record and record[self.column_name] == key:
                            results.append(record)
                            pos += 1
                        else:
                            break
        
        aux_records = self._read_records_from_file(self.aux_file)
        for record in aux_records:
            if record[self.column_name] == key:
                results.append(record)
        
        return results
    
    def _read_record_at_position(self, file_path: str, position: int) -> Optional[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return None

        self.io_stats['disk_reads'] += 1  
        with open(file_path, 'rb') as f:
            f.seek(position * self.record_size)
            data = f.read(self.record_size)

            if len(data) < self.record_size:
                return None

            try:
                record = DynamicRecord.unpack(self.table_schema, data)
                if record.deleted:
                    return None

                record_dict = {}
                for col in self.table_schema:
                    record_dict[col.name] = getattr(record, col.name)

                return record_dict
            except (UnicodeDecodeError, struct.error):
                return None
    
    def rangeSearch(self, begin_key: Any, end_key: Any, begin_inclusive: bool = True, end_inclusive: bool = True) -> List[Dict[str, Any]]:
        results = []
        
        if self._max_bound is not None and begin_key is not None and begin_key > self._max_bound:
            return []
        if self._min_bound is not None and end_key is not None and end_key < self._min_bound:
            return []
            
        if os.path.exists(self.main_file):
            total_records = self._main_record_count
            if total_records > 0:
                left, right = 0, total_records - 1
                start_pos = -1
                
                while left <= right:
                    mid = (left + right) // 2
                    record = self._read_record_at_position(self.main_file, mid)
                    
                    if record is None:
                        break
                    
                    mid_key = record[self.column_name]
                    
                    if (begin_inclusive and mid_key >= begin_key) or (not begin_inclusive and mid_key > begin_key):
                        start_pos = mid
                        right = mid - 1
                    else:
                        left = mid + 1
                
                left, right = 0, total_records - 1
                end_pos = -1
                
                while left <= right:
                    mid = (left + right) // 2
                    record = self._read_record_at_position(self.main_file, mid)
                    
                    if record is None:
                        break
                    
                    mid_key = record[self.column_name]
                    
                    if (end_inclusive and mid_key <= end_key) or (not end_inclusive and mid_key < end_key):
                        end_pos = mid
                        left = mid + 1
                    else:
                        right = mid - 1
                
                if start_pos != -1 and end_pos != -1 and start_pos <= end_pos:
                    for pos in range(start_pos, end_pos + 1):
                        record = self._read_record_at_position(self.main_file, pos)
                        if record:
                            results.append(record)
        
        aux_records = self._read_records_from_file(self.aux_file)
        for record in aux_records:
            key_value = record[self.column_name]
            start_condition = (begin_inclusive and key_value >= begin_key) or (not begin_inclusive and key_value > begin_key)
            end_condition = (end_inclusive and key_value <= end_key) or (not end_inclusive and key_value < end_key)
            if start_condition and end_condition:
                results.append(record)
        
        return results
    
    def bulk_load(self, records: List[Dict[str, Any]]) -> bool:
        if not records:
            return True

        valid_records = [r for r in records if self.column_name in r]

        if not valid_records:
            return False
        
        # Ordenamos los registros segun la columna de indice
        sorted_records = sorted(valid_records, key=lambda x: x[self.column_name])

        if self._main_record_count == 0:
            #Si no tenemos registros en el archivo principal, simplemente escribimos los registros ordenados
            self._write_all_records_to_file(self.main_file, sorted_records)
            self._main_record_count = len(sorted_records)
            
            values = [r[self.column_name] for r in sorted_records]
            self._min_bound = min(values)
            self._max_bound = max(values)

            return True
        else:
            #Si tenemos registros en el archivo principal, leemos todos los registros, los combinamos con los nuevos registros ordenados y reescribimos el archivo principal
            main_records = self._read_records_from_file(self.main_file)
            all_records = main_records + sorted_records
            all_records.sort(key=lambda x: x[self.column_name])

            self._write_all_records_to_file(self.main_file, all_records)
            self._main_record_count = len(all_records)

            values = [r[self.column_name] for r in all_records]
            self._min_bound = min(values)
            self._max_bound = max(values)

            self.io_stats['disk_writes'] += 1  
            with open(self.aux_file, 'wb') as f:
                pass

            return True

    def add(self, record: Dict[str, Any]) -> bool:
        if self.column_name not in record:
            return False

        value = record[self.column_name]
        if self._min_bound is None or value < self._min_bound:
            self._min_bound = value
        if self._max_bound is None or value > self._max_bound:
            self._max_bound = value

        self._write_record_to_file(self.aux_file, record)

        aux_count = self._get_aux_count()
        max_aux = self.calcular_Aux()

        if aux_count >= max_aux:
            self._reconstruct_file()

        return True
    
    def _reconstruct_file(self):
        main_records = self._read_records_from_file(self.main_file)
        aux_records = self._read_records_from_file(self.aux_file)
        
        all_records = main_records + aux_records
        all_records.sort(key=lambda x: x[self.column_name])
        
        self._write_all_records_to_file(self.main_file, all_records)
        
        self._main_record_count = len(all_records)
        
        if all_records:
            values = [r[self.column_name] for r in all_records]
            self._min_bound = min(values)
            self._max_bound = max(values)
        else:
            self._min_bound = None
            self._max_bound = None
        
        self.io_stats['disk_writes'] += 1 
        with open(self.aux_file, 'wb') as f:
            pass
    
    def remove(self, key: Any) -> bool:
        removed_count = 0
        
        main_records = self._read_records_from_file(self.main_file)
        filtered_main = [r for r in main_records if r[self.column_name] != key]
        main_removed = len(main_records) - len(filtered_main)
        removed_count += main_removed
        
        if main_removed > 0:
            self._write_all_records_to_file(self.main_file, filtered_main)
            self._main_record_count -= main_removed
        
        aux_records = self._read_records_from_file(self.aux_file)
        filtered_aux = [r for r in aux_records if r[self.column_name] != key]
        aux_removed = len(aux_records) - len(filtered_aux)
        removed_count += aux_removed
        
        if aux_removed > 0:
            self._write_all_records_to_file(self.aux_file, filtered_aux)
        
        return removed_count > 0