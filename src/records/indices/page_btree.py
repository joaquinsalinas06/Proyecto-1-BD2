from __future__ import annotations
import struct
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar, Deque, List, Dict, Any, Protocol
from collections import deque

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
            children: BLOCK_FACTOR * i
            keys: (BLOCK_FACTOR - 1) * key_codec.fmt   (dinámico, secondary atr)
            refs: (BLOCK_FACTOR - 1) * q               (PK, int)
            deleted: i (-2: no)
    """
    def __init__(self,
                 block_factor: int,
                 key_codec: KeyCodec,
                 is_leaf: bool = False,
                 next_page: int = -1):
        
        self.BLOCK_FACTOR = block_factor
        self.K = self.BLOCK_FACTOR - 1
        self.key_codec = key_codec

        # format keys dynamic
        keys_fmt = ''.join([self.key_codec.fmt for _ in range(self.K)])
        self.HEADER_FORMAT = f"<iBii{self.BLOCK_FACTOR}i" + keys_fmt + f"{self.K}q"

        self.HEADER_SIZE = struct.calcsize(self.HEADER_FORMAT)
        self.SIZE_OF_PAGE = self.HEADER_SIZE

        default_key = '' if isinstance(self.key_codec, FixedStrCodec) else 0
        self.keys: List[Any] = [default_key] * self.K           # secondary atr 
        self.children: List[int] = [-1] * self.BLOCK_FACTOR     # pointers to children
        self.refs: List[int] = [-1] * self.K                    # PK 
        self.count: int = 0
        self.is_leaf: bool = is_leaf
        self.next_page: int = next_page
        self.deleted = -2
    
    def pack(self) -> bytes:
        if not (0 <= self.count <= self.K):
            raise ValueError("count out of range")

        keys_bin = [self.key_codec.to_bin(k) for k in self.keys]
        return struct.pack(
            self.HEADER_FORMAT,
            self.count,
            int(self.is_leaf),
            self.next_page,
            self.deleted,
            *self.children,
            *keys_bin,
            *self.refs,
        )
    
    @staticmethod
    def unpack(data: bytes, key_codec: KeyCodec, BLOCK_FACTOR: int) -> "Page":
        K = BLOCK_FACTOR - 1
        keys_fmt = ''.join([key_codec.fmt for _ in range(K)])
        HEADER_FORMAT = f"<iBii{BLOCK_FACTOR}i" + keys_fmt + f"{K}q"

        tup = struct.unpack_from(HEADER_FORMAT, data, 0)
        off = 0
        count = tup[off]; off += 1
        is_leaf = bool(tup[off]); off += 1
        next_page = tup[off]; off += 1
        deleted = tup[off]; off += 1

        children = list(tup[off : off + BLOCK_FACTOR]); off += BLOCK_FACTOR
        raw_keys = list(tup[off : off + K]); off += K
        refs = list(tup[off : off + K]); off += K

        p = Page(key_codec=key_codec, is_leaf=is_leaf, next_page=next_page, block_factor=BLOCK_FACTOR)
        p.count = count
        p.deleted = deleted
        p.children[:] = children
        p.keys[:] = [key_codec.from_bin(x) for x in raw_keys]
        p.refs[:] = refs
        return p
    
    # ---------------------------------
    # ||            UTILS            ||
    # ---------------------------------

    @staticmethod
    def compute_format(block_factor: int, key_codec: KeyCodec) -> str:
        K = block_factor - 1
        keys_fmt = ''.join([key_codec.fmt for _ in range(K)])
        return f"<iBii{block_factor}i" + keys_fmt + f"{K}q"

    @staticmethod
    def page_size(block_factor: int, key_codec: KeyCodec) -> int:
        return struct.calcsize(Page.compute_format(block_factor, key_codec))

    def __repr__(self) -> str:
        typ = "Leaf" if self.is_leaf else "Internal"
        if self.is_leaf:
            return f"Page({typ}, count={self.count}, keys={self.keys}, refs={self.refs}, next_page={self.next_page})"
        else:
            return f"Page({typ}, count={self.count}, keys={self.keys}, children={self.children})"
