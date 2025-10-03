import os
import struct
from typing import Any, Dict, List, Optional, Tuple

try:
    from ...parser.ast import DataType  
except Exception:  
    from enum import Enum
    class DataType(Enum):
        INT = 0
        FLOAT = 1

from .base_index import BaseIndex

HEADER_FMT = '<IIQ'
HEADER_SIZE = struct.calcsize(HEADER_FMT)

DIR_ENTRY_FMT = '<Q'
DIR_ENTRY_SIZE = struct.calcsize(DIR_ENTRY_FMT)

BUCKET_HDR_FMT = '<II'
BUCKET_HDR_SIZE = struct.calcsize(BUCKET_HDR_FMT)

class ExtendibleHashIndex(BaseIndex):
    def __init__(
        self,
        column_name: str,
        filename: Optional[str] = None,
        is_primary: bool = False,
        primary_key_column: Optional[str] = None,
        bucket_capacity: int = 4,
        pk_data_type: Optional["DataType"] = None,
    ):
       
        super().__init__(column_name, filename, is_primary, primary_key_column)

        self.index_path = filename or f"{column_name}_hash.dat"
        self.bucket_capacity = int(bucket_capacity)

        self.pk_data_type: DataType = pk_data_type if pk_data_type is not None else DataType.INT

        if self.pk_data_type == DataType.INT:
            self.entry_fmt = '<qq'
        elif self.pk_data_type == DataType.FLOAT:
            self.entry_fmt = '<qd'
        else:
            raise ValueError(f"Hash index solo soporta PK de tipo INT o FLOAT; recibido: {self.pk_data_type}")
        self.entry_size = struct.calcsize(self.entry_fmt)

        if not os.path.exists(self.index_path):
            self._init_new()
        else:
            with open(self.index_path, 'rb') as f:
                self._read_header(f)  

    def _write_header(self, f, global_depth: int, bucket_capacity: int, directory_offset: int) -> None:
        f.seek(0)
        f.write(struct.pack(HEADER_FMT, global_depth, bucket_capacity, directory_offset))

    def _read_header(self, f) -> Tuple[int, int, int]:
        f.seek(0)
        raw = f.read(HEADER_SIZE)
        if len(raw) != HEADER_SIZE:
            raise ValueError('Header vacío o corrupto')
        return struct.unpack(HEADER_FMT, raw)

    def _write_directory_at_end(self, f, directory_offsets: List[int]) -> int:
        f.seek(0, os.SEEK_END)
        start = f.tell()
        fmt = '<' + 'Q' * len(directory_offsets)
        f.write(struct.pack(fmt, *directory_offsets))
        return start

    def _read_directory(self, f, start_offset: int, global_depth: int) -> List[int]:
        f.seek(start_offset)
        M = 1 << global_depth
        raw = f.read(M * DIR_ENTRY_SIZE)
        if len(raw) != M * DIR_ENTRY_SIZE:
            raise ValueError('Directorio corrupto')
        return list(struct.unpack('<' + 'Q' * M, raw))

    def _read_bucket(self, f, bucket_offset: int, bucket_capacity: int) -> Tuple[int, List[Tuple[int, Any]]]:
        f.seek(bucket_offset)
        hdr = f.read(BUCKET_HDR_SIZE)
        if len(hdr) != BUCKET_HDR_SIZE:
            raise ValueError('Bucket corrupto (header)')
        local_depth, count = struct.unpack(BUCKET_HDR_FMT, hdr)

        raw = f.read(bucket_capacity * self.entry_size)
        if len(raw) != bucket_capacity * self.entry_size:
            raise ValueError('Bucket corrupto (entries)')

        pairs = list(struct.iter_unpack(self.entry_fmt, raw))
        return local_depth, pairs[:count]

    def _write_bucket(self, f, bucket_offset: int, local_depth: int,
                      bucket_capacity: int, entries: List[Tuple[int, Any]]) -> None:
        count = min(len(entries), bucket_capacity)
        f.seek(bucket_offset)
        f.write(struct.pack(BUCKET_HDR_FMT, local_depth, count))
        zero_pk = 0 if self.pk_data_type == DataType.INT else 0.0
        to_write = entries[:count] + [(0, zero_pk)] * (bucket_capacity - count)
        f.write(b''.join(struct.pack(self.entry_fmt, h, pk) for (h, pk) in to_write))

    def _append_bucket(self, f, local_depth: int, bucket_capacity: int) -> int:
        f.seek(0, os.SEEK_END)
        off = f.tell()
        self._write_bucket(f, off, local_depth, bucket_capacity, [])
        return off

    def search(self, key: Any) -> List[Dict[str, Any]]:
        hkey = self._hash(key)
        with open(self.index_path, 'rb') as f:
            D, B, dir_off = self._read_header(f)
            i = self._dir_index(hkey, D)
            directory = self._read_directory(f, dir_off, D)
            bucket_off = directory[i]
            _, pairs = self._read_bucket(f, bucket_off, B)

        pk_name = self.primary_key_column
        out: List[Dict[str, Any]] = []
        for (hk, pk) in pairs:
            if hk == hkey:
                out.append({pk_name: pk})
        return out

    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        raise NotImplementedError('Hash index no soporta rangos')

    def add(self, record: Dict[str, Any]) -> bool:
        if self.column_name not in record or self.primary_key_column not in record:
            return False

        sec_val = record[self.column_name]
        pk_val_any = record[self.primary_key_column]
        hkey = self._hash(sec_val)

        if self.pk_data_type == DataType.INT:
            pk_val = int(pk_val_any)
        elif self.pk_data_type == DataType.FLOAT:
            pk_val = float(pk_val_any)
        else:
            raise ValueError('Tipo de PK no soportado')

        while True:
            with open(self.index_path, 'rb+') as f:
                D, B, dir_off = self._read_header(f)
                i = self._dir_index(hkey, D)
                directory = self._read_directory(f, dir_off, D)
                bucket_off = directory[i]
                local_d, pairs = self._read_bucket(f, bucket_off, B)

                if len(pairs) < B:
                    pairs.append((hkey, pk_val))
                    self._write_bucket(f, bucket_off, local_d, B, pairs)
                    return True
            self._split_bucket(i, D, B, directory)

    def remove(self, key: Any) -> bool:
        hkey = self._hash(key)
        with open(self.index_path, 'rb+') as f:
            D, B, dir_off = self._read_header(f)
            i = self._dir_index(hkey, D)
            directory = self._read_directory(f, dir_off, D)
            bucket_off = directory[i]
            local_d, pairs = self._read_bucket(f, bucket_off, B)

            before = len(pairs)
            pairs = [(hk, pk) for (hk, pk) in pairs if hk != hkey]
            if len(pairs) != before:
                self._write_bucket(f, bucket_off, local_d, B, pairs)
                return True
        return False

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
            local_d, old_pairs = self._read_bucket(f, old_off, bucket_capacity)
            D = global_depth

            if local_d == D:
                D = D + 1
                directory = directory + directory

            new_off = self._append_bucket(f, local_d + 1, bucket_capacity)
            new_local_d = local_d + 1
            self._write_bucket(f, old_off, new_local_d, bucket_capacity, old_pairs)

            stride = 1 << new_local_d
            half = stride // 2
            M = 1 << D
            block_start = (split_index // stride) * stride
            for j in range(block_start, min(block_start + stride, M)):
                if directory[j] == old_off and (j - block_start) >= half:
                    directory[j] = new_off

            _, pairs = self._read_bucket(f, old_off, bucket_capacity)  
            left: List[Tuple[int, Any]] = []
            right: List[Tuple[int, Any]] = []
            for (hk, pk) in pairs:
                idx = self._dir_index(hk, D)
                bstart = (idx // stride) * stride
                if (idx - bstart) >= half:
                    right.append((hk, pk))
                else:
                    left.append((hk, pk))

            self._write_bucket(f, old_off, new_local_d, bucket_capacity, left)
            self._write_bucket(f, new_off, new_local_d, bucket_capacity, right)

            new_dir_off = self._write_directory_at_end(f, directory)
            self._write_header(f, D, bucket_capacity, new_dir_off)

    def _init_new(self) -> None:
        with open(self.index_path, 'wb') as f:
            D = 1
            B = self.bucket_capacity
            self._write_header(f, D, B, 0)  

            off0 = self._append_bucket(f, local_depth=1, bucket_capacity=B)
            off1 = self._append_bucket(f, local_depth=1, bucket_capacity=B)

            directory = [off0, off1]  
            dir_off = self._write_directory_at_end(f, directory)

            self._write_header(f, D, B, dir_off)
