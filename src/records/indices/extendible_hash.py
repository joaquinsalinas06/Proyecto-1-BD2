import os
import struct
from typing import Any, Dict, List, Optional, Tuple

from .base_index import BaseIndex

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
        bucket_capacity: int = 4,
    ):
       
        super().__init__(column_name, filename, is_primary, primary_key_column)

        self.bucket_capacity = int(bucket_capacity)
        self.index_path = filename or f"{column_name}_hash.dat"

        if not os.path.exists(self.index_path):
            self._init_new()
        else:
            with open(self.index_path, 'rb') as f:
                _read_header(f)  


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

    def add(self, record: Dict[str, Any]) -> bool:
        if self.column_name not in record or self.primary_key_column not in record:
            return False

        sec_val = record[self.column_name]
        pk_val = int(record[self.primary_key_column])
        hkey = self._hash(sec_val)

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
                        pairs.append((hkey, pk_val))
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
                    _write_bucket(f, new_overflow_off, last_local_d, B, [(hkey, pk_val)], 0)
                    _write_bucket(f, last_bucket_off, last_local_d, B, last_pairs, new_overflow_off)
                    return True

            self._split_bucket(i, D, B, directory)

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
                    pairs = [(hk, pk) for hk, pk in pairs if not (hk == hkey and pk == int(primary_key))]
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
                if (idx - bstart) >=  mid:
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


    def _init_new(self) -> None:
        with open(self.index_path, 'wb') as f:
            B = self.bucket_capacity
            _write_header(f, 1, B, 0)
            
            off0 = _append_bucket(f, 1, B)
            off1 = _append_bucket(f, 1, B)
            
            dir_off = _write_directory_at_end(f, [off0, off1])
            _write_header(f, 1, B, dir_off)
