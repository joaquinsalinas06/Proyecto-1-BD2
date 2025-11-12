from __future__ import annotations

import os
import struct
import pickle
import heapq
import itertools
import math
from typing import Dict, List, Optional, Tuple, TypeAlias, Iterable

DOC_HEADER_FORMAT = "<i"        
DOC_RECORD_FORMAT = "<16si"  
DOC_HEADER_SIZE = struct.calcsize(DOC_HEADER_FORMAT)
DOC_RECORD_SIZE = struct.calcsize(DOC_RECORD_FORMAT)

def _encode_doc_id(doc_id: str) -> bytes:
    b = doc_id.encode("utf-8")[:16]
    return b.ljust(16, b"\x00")


def _decode_doc_id(raw: bytes) -> str:
    return raw.rstrip(b"\x00").decode("utf-8", errors="ignore")


class DocumentFile:
    def __init__(self, filename: str):
        self.filename = filename

        if not os.path.exists(filename):
            with open(filename, "wb") as f:
                f.write(struct.pack(DOC_HEADER_FORMAT, 0))

    def _read_header(self) -> int:
        with open(self.filename, "rb") as f:
            data = f.read(DOC_HEADER_SIZE)
            return struct.unpack(DOC_HEADER_FORMAT, data)[0] if len(data) == DOC_HEADER_SIZE else 0

    def _write_header(self, num_docs: int) -> None:
        with open(self.filename, "r+b") as f:
            f.seek(0)
            f.write(struct.pack(DOC_HEADER_FORMAT, num_docs))

    def append(self, doc_id: str, term_count: int) -> int:
        num_docs = self._read_header()
        with open(self.filename, "r+b") as f:
            f.seek(DOC_HEADER_SIZE + num_docs * DOC_RECORD_SIZE)
            f.write(struct.pack(DOC_RECORD_FORMAT, _encode_doc_id(doc_id), term_count))
        self._write_header(num_docs + 1)
        return num_docs  # position where it was written

    def read(self, pos: int) -> Optional[Tuple[str, int]]:
        with open(self.filename, "rb") as f:
            f.seek(DOC_HEADER_SIZE + pos * DOC_RECORD_SIZE)
            data = f.read(DOC_RECORD_SIZE)
            if len(data) != DOC_RECORD_SIZE:
                return None
            doc_id_raw, term_count = struct.unpack(DOC_RECORD_FORMAT, data)
            return _decode_doc_id(doc_id_raw), term_count

    def show(self) -> None:
        n = self._read_header()
        for i in range(n):
            print(f"Record {i}: {self.read(i)}")
