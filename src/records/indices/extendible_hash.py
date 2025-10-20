import os
import struct
import math
from typing import Any, Dict, List, Optional, Tuple

from .base_index import BaseIndex


def calcular_Capacidad(expected_records: Optional[int] = None) -> int:
    if expected_records is None:
        return 64

    optimal = int(math.sqrt(expected_records) / 2)
    
    if optimal < 2:
        power_of_2 = 16
    else:
        power_of_2 = 2 ** round(math.log2(optimal))
    
    return max(16, min(512, power_of_2))

HEADER_FMT = 'IIQ'
HEADER_SIZE = struct.calcsize(HEADER_FMT)

DIR_ENTRY_FMT = 'Q'
DIR_ENTRY_SIZE = struct.calcsize(DIR_ENTRY_FMT)

BUCKET_HDR_FMT = 'IIQ'
BUCKET_HDR_SIZE = struct.calcsize(BUCKET_HDR_FMT)
ENTRY_FMT = 'qq'
ENTRY_SIZE = struct.calcsize(ENTRY_FMT)


def _write_header(f, global_depth: int, bucket_capacity: int, directory_offset: int) -> None:
    f.seek(0)
    f.write(struct.pack(HEADER_FMT, global_depth, bucket_capacity, directory_offset))


def _read_header(f) -> Tuple[int, int, int]:
    f.seek(0)
    raw = f.read(HEADER_SIZE)
    if len(raw) != HEADER_SIZE:
        raise ValueError('Header vacío o corrupto')
    return struct.unpack(HEADER_FMT, raw)


def _write_directory_at_end(f, directory_offsets: List[int]) -> int:
    f.seek(0, os.SEEK_END)
    start = f.tell()
    fmt = '<' + 'Q' * len(directory_offsets)
    f.write(struct.pack(fmt, *directory_offsets))
    return start


def _read_directory(f, start_offset: int, global_depth: int) -> List[int]:
    f.seek(start_offset)
    M = 1 << global_depth
    raw = f.read(M * DIR_ENTRY_SIZE)
    if len(raw) != M * DIR_ENTRY_SIZE:
        raise ValueError('Directorio corrupto')
    return list(struct.unpack('<' + 'Q' * M, raw))


def _read_bucket(f, bucket_offset: int, bucket_capacity: int) -> Tuple[int, List[Tuple[int, int]], int]:
    f.seek(bucket_offset)
    hdr = f.read(BUCKET_HDR_SIZE)
    if len(hdr) != BUCKET_HDR_SIZE:
        raise ValueError('Bucket corrupto (header)')
    local_depth, count, overflow_next = struct.unpack(BUCKET_HDR_FMT, hdr)

    raw = f.read(bucket_capacity * ENTRY_SIZE)
    if len(raw) != bucket_capacity * ENTRY_SIZE:
        raise ValueError('Bucket corrupto (entries)')

    pairs = list(struct.iter_unpack(ENTRY_FMT, raw))
    return local_depth, pairs[:count], overflow_next


def _write_bucket(f, bucket_offset: int, local_depth: int,
                  bucket_capacity: int, entries: List[Tuple[int, int]], overflow_next: int = 0) -> None:
    count = min(len(entries), bucket_capacity)
    f.seek(bucket_offset)
    f.write(struct.pack(BUCKET_HDR_FMT, local_depth, count, overflow_next))
    to_write = entries[:count] + [(0, 0)] * (bucket_capacity - count)
    f.write(b''.join(struct.pack(ENTRY_FMT, h, pk) for (h, pk) in to_write))


def _append_bucket(f, local_depth: int, bucket_capacity: int) -> int:
    f.seek(0, os.SEEK_END)
    off = f.tell()
    _write_bucket(f, off, local_depth, bucket_capacity, [])
    return off



class ExtendibleHashIndex(BaseIndex):
    def __init__(
        self,
        column_name: str,
        filename: Optional[str] = None,
        is_primary: bool = False,
        primary_key_column: Optional[str] = None,
        bucket_capacity: int = None,
        expected_size: Optional[int] = None
    ):
        super().__init__(column_name, filename, is_primary, primary_key_column)

        if bucket_capacity is None:
            bucket_capacity = calcular_Capacidad(expected_size)
        
        self.bucket_capacity = int(bucket_capacity)
        self.index_path = self.filename

        if not os.path.exists(self.index_path):
            self._init_new(expected_size=expected_size)
        else:
            with open(self.index_path, 'rb') as f:
                D, B, dir_off = _read_header(f)


    def search(self, key: Any) -> List[Dict[str, Any]]:
        hkey = self._hash(key)
        results = []
        with open(self.index_path, 'rb') as f:
            D, B, dir_off = _read_header(f)
            i = self._dir_index(hkey, D)
            directory = _read_directory(f, dir_off, D)
            bucket_off = directory[i]

            while bucket_off != 0:
                _, pairs, overflow_next = _read_bucket(f, bucket_off, B)
                for hk, pk in pairs:
                    if hk == hkey:
                        results.append({self.primary_key_column: pk})
                bucket_off = overflow_next

        return results

    def rangeSearch(self, begin_key: Any, end_key: Any,
                   begin_inclusive: bool = True, end_inclusive: bool = True) -> List[Dict[str, Any]]:
        raise NotImplementedError('Hash index no soporta rangos')

    def bulk_load(self, records: List[Dict[str, Any]]) -> int:
        loaded = 0

        entries_to_insert = []
        # Recorremos todos los registros para extraer las claves hash y las claves primarias
        for record in records:
            if self.column_name not in record or self.primary_key_column not in record:
                continue
            
            sec_val = record[self.column_name]
            pk_val = record[self.primary_key_column]
            
            if isinstance(pk_val, (int, float)):
                pk_val_int = int(pk_val)
            else:
                pk_val_int = abs(hash(str(pk_val)))
            
            hkey = self._hash(sec_val)
            entries_to_insert.append((hkey, pk_val_int))
        #Abriendo el archivo una sola vez para insertar todos los registros
        with open(self.index_path, 'rb+') as f:
            for _, (hkey, pk_val_int) in enumerate(entries_to_insert):
                if self._add_entry_with_open_file(f, hkey, pk_val_int):
                    loaded += 1

        return loaded

    # Esta función asume que el archivo ya está abierto y usa la logica de inserción defniida en el add
    def _add_entry_with_open_file(self, f, hkey: int, pk_val_int: int) -> bool:
        while True:
            D, B, dir_off = _read_header(f)
            i = self._dir_index(hkey, D)
            directory = _read_directory(f, dir_off, D)
            bucket_off = directory[i]

            current_off = bucket_off
            prev_off = 0
            while current_off != 0:
                local_d, pairs, overflow_next = _read_bucket(f, current_off, B)
                if len(pairs) < B:
                    pairs.append((hkey, pk_val_int))
                    _write_bucket(f, current_off, local_d, B, pairs, overflow_next)
                    f.flush()
                    return True
                prev_off = current_off
                current_off = overflow_next

            all_hashes = set([hkey])
            chain_off = bucket_off
            while chain_off != 0:
                _, chain_pairs, chain_next = _read_bucket(f, chain_off, B)
                all_hashes.update(hk for hk, _ in chain_pairs)
                chain_off = chain_next

            if len(all_hashes) == 1:
                last_bucket_off = prev_off if prev_off != 0 else bucket_off
                last_local_d, last_pairs, _ = _read_bucket(f, last_bucket_off, B)
                new_overflow_off = _append_bucket(f, last_local_d, B)
                _write_bucket(f, new_overflow_off, last_local_d, B, [(hkey, pk_val_int)], 0)
                _write_bucket(f, last_bucket_off, last_local_d, B, last_pairs, new_overflow_off)
                f.flush()
                return True
            self._split_bucket_with_open_file(f, i, D, B, directory)

    #Se estandariza la logica de inserción en esta función, siendo la función pública add la que abre el archivo
    def _add_entry(self, hkey: int, pk_val_int: int) -> bool:
        while True:
            with open(self.index_path, 'rb+') as f:
                D, B, dir_off = _read_header(f)
                i = self._dir_index(hkey, D)
                directory = _read_directory(f, dir_off, D)
                bucket_off = directory[i]

                current_off = bucket_off
                prev_off = 0
                while current_off != 0:
                    local_d, pairs, overflow_next = _read_bucket(f, current_off, B)
                    if len(pairs) < B:
                        pairs.append((hkey, pk_val_int))
                        _write_bucket(f, current_off, local_d, B, pairs, overflow_next)
                        return True
                    prev_off = current_off
                    current_off = overflow_next

                all_hashes = set([hkey])
                chain_off = bucket_off
                while chain_off != 0:
                    _, chain_pairs, chain_next = _read_bucket(f, chain_off, B)
                    all_hashes.update(hk for hk, _ in chain_pairs)
                    chain_off = chain_next

                if len(all_hashes) == 1:
                    last_bucket_off = prev_off if prev_off != 0 else bucket_off
                    last_local_d, last_pairs, _ = _read_bucket(f, last_bucket_off, B)
                    new_overflow_off = _append_bucket(f, last_local_d, B)
                    _write_bucket(f, new_overflow_off, last_local_d, B, [(hkey, pk_val_int)], 0)
                    _write_bucket(f, last_bucket_off, last_local_d, B, last_pairs, new_overflow_off)
                    return True

            self._split_bucket(i, D, B, directory)

    # Add pasa a hashear la clave y llamar a la función de inserción
    def add(self, record: Dict[str, Any]) -> bool:
        if self.column_name not in record or self.primary_key_column not in record:
            return False

        sec_val = record[self.column_name]
        pk_val = record[self.primary_key_column]
        if isinstance(pk_val, (int, float)):
            pk_val_int = int(pk_val)
        else:
            pk_val_int = abs(hash(str(pk_val)))
        hkey = self._hash(sec_val)
        
        return self._add_entry(hkey, pk_val_int)

    def remove(self, key: Any, primary_key: Optional[Any] = None) -> bool:
        hkey = self._hash(key)
        removed = False

        with open(self.index_path, 'rb+') as f:
            D, B, dir_off = _read_header(f)
            i = self._dir_index(hkey, D)
            directory = _read_directory(f, dir_off, D)
            current_off = directory[i]

            while current_off != 0:
                local_d, pairs, overflow_next = _read_bucket(f, current_off, B)
                before = len(pairs)

                if primary_key is not None:
                    if isinstance(primary_key, str):
                        pk_int = abs(hash(primary_key))
                    else:
                        pk_int = int(primary_key)
                    pairs = [(hk, pk) for hk, pk in pairs if not (hk == hkey and pk == pk_int)]
                else:
                    pairs = [(hk, pk) for hk, pk in pairs if hk != hkey]

                if len(pairs) != before:
                    _write_bucket(f, current_off, local_d, B, pairs, overflow_next)
                    removed = True
                    if primary_key is not None:
                        return True

                current_off = overflow_next

        return removed

    def getAllRecords(self) -> List[Dict[str, Any]]:
        all_records = []
        with open(self.index_path, 'rb') as f:
            D, B, dir_off = _read_header(f)
            directory = _read_directory(f, dir_off, D)

            sorted_dir = sorted(directory)
            last_processed = None

            for bucket_off in sorted_dir:

                if bucket_off == last_processed:
                    continue
                last_processed = bucket_off

                current_off = bucket_off

                while current_off != 0:
                    _, pairs, overflow_next = _read_bucket(f, current_off, B)
                    for _, pk in pairs:
                        all_records.append({self.primary_key_column: pk})
                    current_off = overflow_next

        return all_records

    def clear_all(self) -> int:
        count = len(self.getAllRecords()) if os.path.exists(self.index_path) else 0

        if os.path.exists(self.index_path):
            os.remove(self.index_path)

        self._init_new()
        return count

    def _hash(self, key: Any) -> int:
        if isinstance(key, int):
            return abs(key)
        if isinstance(key, float):
            return abs(int(key * 1_000_000))
        if isinstance(key, str):
            return abs(hash(key))
        return abs(hash(str(key)))

    def _dir_index(self, hash_key: int, global_depth: int) -> int:
        return hash_key % (1 << global_depth)

    def _split_bucket(self, split_index: int, global_depth: int,
                      bucket_capacity: int, directory: List[int]) -> None:
        with open(self.index_path, 'rb+') as f:
            self._split_bucket_with_open_file(f, split_index, global_depth, bucket_capacity, directory)

    # en vez de abrir el archivo, se pasa el archivo abierto, funciona tanto para el split bucket como para el bulk load
    def _split_bucket_with_open_file(self, f, split_index: int, global_depth: int,
                                     bucket_capacity: int, directory: List[int]) -> None:
        old_off = directory[split_index]
        local_d, _, _ = _read_bucket(f, old_off, bucket_capacity)
        D = global_depth

        if local_d == D:
            D += 1
            directory = directory + directory

        new_off = _append_bucket(f, local_d + 1, bucket_capacity)
        new_local_d = local_d + 1

        stride = 1 << new_local_d
        mid = stride // 2
        M = 1 << D

        for j in range(M):
            if directory[j] == old_off:
                direct = j % stride
                if direct >= mid:
                    directory[j] = new_off

        all_pairs = []
        current_off = old_off
        visited = set()
        while current_off != 0 and current_off not in visited:
            visited.add(current_off)
            _, pairs, overflow_next = _read_bucket(f, current_off, bucket_capacity)
            all_pairs.extend(pairs)
            current_off = overflow_next

        left, right = [], []
        for hk, pk in all_pairs:
            idx = self._dir_index(hk, D)
            bstart = (idx // stride) * stride
            if (idx - bstart) >= mid:
                right.append((hk, pk))
            else:
                left.append((hk, pk))

        self._write_bucket_with_overflow(f, old_off, new_local_d, bucket_capacity, left)
        self._write_bucket_with_overflow(f, new_off, new_local_d, bucket_capacity, right)

        new_dir_off = _write_directory_at_end(f, directory)
        _write_header(f, D, bucket_capacity, new_dir_off)
        f.flush()

    def _write_bucket_with_overflow(self, f, bucket_off: int, local_depth: int,
                                    bucket_capacity: int, all_pairs: List[Tuple[int, int]]) -> None:
        if not all_pairs:
            _write_bucket(f, bucket_off, local_depth, bucket_capacity, [], 0)
            return

        main_pairs = all_pairs[:bucket_capacity]
        remaining = all_pairs[bucket_capacity:]

        if not remaining:
            _write_bucket(f, bucket_off, local_depth, bucket_capacity, main_pairs, 0)
            return

        overflow_buckets = []
        for i in range(0, len(remaining), bucket_capacity):
            chunk = remaining[i:i+bucket_capacity]
            overflow_off = _append_bucket(f, local_depth, bucket_capacity)
            overflow_buckets.append((overflow_off, chunk))

        for idx, (off, pairs) in enumerate(overflow_buckets):
            next_off = overflow_buckets[idx + 1][0] if idx + 1 < len(overflow_buckets) else 0
            _write_bucket(f, off, local_depth, bucket_capacity, pairs, next_off)

        first_overflow = overflow_buckets[0][0]
        _write_bucket(f, bucket_off, local_depth, bucket_capacity, main_pairs, first_overflow)


    def _init_new(self, expected_size: Optional[int] = None) -> None:
        with open(self.index_path, 'wb') as f:
            B = self.bucket_capacity
            init_depth = 1
            if expected_size and expected_size > B * 2:
                buckets_necesitados = expected_size / (B * 0.7)
                calc_depth = max(1, int(math.log2(buckets_necesitados)))
                init_depth = min(calc_depth, 12)

            _write_header(f, init_depth, B, 0)

            num_buckets = 1 << init_depth
            bucket_offsets = []
            for _ in range(num_buckets):
                off = _append_bucket(f, init_depth, B)
                bucket_offsets.append(off)

            dir_off = _write_directory_at_end(f, bucket_offsets)
            _write_header(f, init_depth, B, dir_off)
