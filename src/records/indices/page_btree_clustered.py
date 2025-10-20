from __future__ import annotations
import struct
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar, Deque, List, Dict, Any, Protocol
from collections import deque
from ..record import DynamicRecord


class KeyCodec(Protocol):
    fmt: str 
    def to_bin(self, v: Any) -> Any: ...
    def from_bin(self, b: Any) -> Any: ...

class Int64Codec:
    fmt = 'q'  
    def to_bin(self, v: int) -> int:
        return 0 if v is None else int(v)
    def from_bin(self, b: int) -> int:
        return int(b)
    
class FixedStrCodec:
    def __init__(self, size: int = 20):
        self.size = size
        self.fmt = f'{size}s'  
    def to_bin(self, v: str) -> bytes:
        if v is None:
            v = ''
        b = str(v).encode('utf-8')
        return b[:self.size].ljust(self.size, b'\x00')
    def from_bin(self, b: bytes) -> str:
        return b.split(b'\x00', 1)[0].decode('utf-8', errors='ignore')


class Page:
    """
        struct:
            count: i
            is_leaf: B
            next_page: i
            deleted: i (-2: no)
            children: BLOCK_FACTOR * i
            keys: (BLOCK_FACTOR - 1) * key_codec.fmt   (dinámico, pk)
    """
    def __init__(self,
                 block_factor: int,
                 key_codec: KeyCodec,
                 records: Optional[List] = None,
                 is_leaf: bool = False,
                 next_page: int = -1,
                 record_size: int = 0
                 ):
        
        self.BLOCK_FACTOR = block_factor
        self.RECORD_SIZE = record_size
        self.K = self.BLOCK_FACTOR - 1
        self.key_codec = key_codec

        # format keys dynamic
        keys_fmt = ''.join([self.key_codec.fmt for _ in range(self.K)])
        self.HEADER_FORMAT = f"<iBii{self.BLOCK_FACTOR}i" + keys_fmt 

        self.HEADER_SIZE = struct.calcsize(self.HEADER_FORMAT)
        self.SIZE_OF_PAGE = self.HEADER_SIZE + self.K * self.RECORD_SIZE

        default_key = '' if isinstance(self.key_codec, FixedStrCodec) else 0
        self.keys: List[Any] = [default_key] * self.K           # PK
        self.children: List[int] = [-1] * self.BLOCK_FACTOR     # pointers to children
        self.count: int = 0
        self.is_leaf: bool = is_leaf
        self.next_page: int = next_page
        self.deleted = -2

        if records is None:
            self.records = [None] * self.K
        else:
            self.records = (list(records) + [None] * self.K)[:self.K]
    
    def pack(self) -> bytes:

        if not (0 <= self.count <= self.K):
            raise ValueError("count out of range")
        if self.count > 0 and self.RECORD_SIZE <= 0:
            raise ValueError(f"RECORD_SIZE must be > 0, ({self.RECORD_SIZE}) when count > 0, ({self.count})")

        # Header
        keys_bin = [self.key_codec.to_bin(k) for k in self.keys]
        header_data = struct.pack(
            self.HEADER_FORMAT,
            self.count,
            int(self.is_leaf),
            self.next_page,
            self.deleted,
            *self.children,
            *keys_bin,
        )
        

        recs = self.records

        record_data = b''
        for record in self.records:
            if record is None:
                record_data += b'\x00' * self.RECORD_SIZE
            else:
                record_data += record.pack()
        return header_data + record_data        
    
    @staticmethod
    def unpack(
            data: bytes, 
            key_codec: KeyCodec, 
            BLOCK_FACTOR: int,
            RECORD_SIZE: int,
            table_schema: List
        ) -> "Page":
        K = BLOCK_FACTOR - 1
        keys_fmt = ''.join([key_codec.fmt for _ in range(K)])
        HEADER_FORMAT = f"<iBii{BLOCK_FACTOR}i" + keys_fmt
        HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

        # header
        tup = struct.unpack_from(HEADER_FORMAT, data, 0)
        off = 0
        count = tup[off]; off += 1
        is_leaf = bool(tup[off]); off += 1
        next_page = tup[off]; off += 1
        deleted = tup[off]; off += 1

        children = list(tup[off : off + BLOCK_FACTOR]); off += BLOCK_FACTOR
        raw_keys = list(tup[off : off + K]); off += K

        offset = HEADER_SIZE
        records: List[DynamicRecord] = []

        for _ in range(count):
            record_data = data[offset: offset + RECORD_SIZE]
            records.append(DynamicRecord.unpack(table_schema, record_data))
            offset += RECORD_SIZE

        p = Page(
            block_factor=BLOCK_FACTOR,
            key_codec=key_codec, 
            records=records,
            is_leaf=is_leaf, 
            next_page=next_page, 
            record_size=RECORD_SIZE
            )
        
        p.count = count
        p.deleted = deleted
        p.children[:] = children
        p.keys[:] = [key_codec.from_bin(x) for x in raw_keys]

        return p
    
    # ---------------------------------
    # ||            UTILS            ||
    # ---------------------------------

    @staticmethod
    def compute_format(block_factor: int, key_codec: KeyCodec) -> str:
        K = block_factor - 1
        keys_fmt = ''.join([key_codec.fmt for _ in range(K)])
        return f"<iBii{block_factor}i" + keys_fmt

    @staticmethod
    def page_size(block_factor: int, key_codec: KeyCodec, record_size: int) -> int:
        header_fmt = Page.compute_format(block_factor, key_codec)
        header_size = struct.calcsize(header_fmt)
        return header_size + (block_factor-1) * record_size

    def __repr__(self) -> str:
        typ = "Leaf" if self.is_leaf else "Internal"
        keys_view = self.keys[:self.count]
        if self.is_leaf:
            return f"Page({typ}, count={self.count}, keys={keys_view}, next_page={self.next_page})"
        else:
            return f"Page({typ}, count={self.count}, keys={keys_view}, children={self.children[:self.count+1]})"
