from __future__ import annotations

import os
import struct
import pickle
import heapq
import itertools
import math
from typing import Dict, List, Optional, Tuple, TypeAlias, Iterable

from document_file import DocumentFile
from utils.text_utils import bow  # bag of words: str -> Dict[str, int]

MEMORY_LIMIT =  8 * 1024 * 1024     
BUCKET_LIMIT = 64 * 1024

Posting: TypeAlias = Dict[str, int]          
BType: TypeAlias = Dict[str, Posting]     

INV_HEADER_FORMAT = "<i"      
INV_HEADER_SIZE = struct.calcsize(INV_HEADER_FORMAT)


def _estimate_bytes_for_record(term: str, postings: Posting) -> int:
    return len(pickle.dumps({term: postings}, protocol=pickle.HIGHEST_PROTOCOL))


def _merge_postings(p1: Posting, p2: Posting) -> Posting:
    if not p1:
        return dict(p2)
    if not p2:
        return dict(p1)
    out: Posting = dict(p1)
    for d, f in p2.items():
        out[d] = out.get(d, 0) + f
    return out

class InvertedFile:
    def __init__(self, filename: str):
        self.filename = filename
        if not os.path.exists(filename):
            with open(filename, "wb") as f:
                f.write(struct.pack(INV_HEADER_FORMAT, 0))

    def _write_header(self, num_buckets: int) -> None:
        with open(self.filename, "r+b") as f:
            f.seek(0)
            f.write(struct.pack(INV_HEADER_FORMAT, num_buckets))

    def _read_header(self) -> int:
        with open(self.filename, "rb") as f:
            data = f.read(INV_HEADER_SIZE)
            return struct.unpack(INV_HEADER_FORMAT, data)[0] if len(data) == INV_HEADER_SIZE else 0

    def _serialize(self, d: BType) -> bytes:
        data = pickle.dumps(d, protocol=pickle.HIGHEST_PROTOCOL)
        if len(data) > BUCKET_LIMIT:
            raise ValueError(f"Bucket excede BUCKET_LIMIT={BUCKET_LIMIT} bytes (len={len(data)}).")
        return data.ljust(BUCKET_LIMIT, b"\x00")

    def _deserialize(self, b: bytes) -> BType:
        if not b:
            return {}
        try:
            return pickle.loads(b.rstrip(b"\x00"))
        except Exception as e:
            return {}

    def read(self, pos: int) -> BType:
        with open(self.filename, "rb") as f:
            f.seek(INV_HEADER_SIZE + pos * BUCKET_LIMIT)
            data = f.read(BUCKET_LIMIT)
            if not data:
                return {}
            return self._deserialize(data)

    def write(self, pos: int, d: BType) -> None:
        data = self._serialize(d)
        with open(self.filename, "r+b") as f:
            f.seek(INV_HEADER_SIZE + pos * BUCKET_LIMIT)
            f.write(data)

    def append(self, d: BType) -> int:
        n = self._read_header()
        data = self._serialize(d)
        with open(self.filename, "r+b") as f:
            f.seek(INV_HEADER_SIZE + n * BUCKET_LIMIT)
            f.write(data)
        self._write_header(n + 1)
        return n

    def show(self) -> None:
        n = self._read_header()
        for i in range(n):
            bucket = self.read(i)
            print(f"Bucket {i}: {bucket}")
            print(len(pickle.dumps(bucket)))


class InvertedIndex:
    def __init__(self, filename: str, docfile_path: Optional[str] = None):
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Archivo {filename} no encontrado.")
        self.filename = filename
        self.file = InvertedFile(filename)
        self.docfile = DocumentFile(docfile_path or (os.path.splitext(filename)[0] + "_doc.dat"))

    # -- utilities --
    @staticmethod
    def _sort_dict(d: BType) -> BType:
        return {term: dict(sorted(postings.items())) for term, postings in sorted(d.items())}

    def build_index(self) -> None:
        B = max(2, MEMORY_LIMIT // BUCKET_LIMIT)
        num_buckets = self.file._read_header()

        # 1) ordenar cada bucket individual
        for i in range(num_buckets):
            d = self.file.read(i)
            self.file.write(i, self._sort_dict(d))

        current_name = self.filename
        active_file = self.file
        round_no = 1
        prev_n = None 

        while True:
            n = active_file._read_header()
            print(f"[DBG] round={round_no}, n={n}, B={B}, fanin={max(1, B-1)}")

            # condición de parada:
            if n <= 1 or n == prev_n:
                break
            prev_n = n

            tmp_name = os.path.splitext(current_name)[0] + f"_tmp_{round_no}.dat"
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
            out = InvertedFile(tmp_name)

            fanin = max(1, B - 1)

            for g in range(0, n, fanin):
                group_ids = list(range(g, min(g + fanin, n)))
                buffers = [active_file.read(bi) for bi in group_ids]
                lists = [sorted(buf.items()) for buf in buffers]
                idxs = [0] * len(lists)

                heap: list[tuple[str, int]] = []
                for src, lst in enumerate(lists):
                    if lst:
                        heapq.heappush(heap, (lst[0][0], src))

                acc: BType = {}
                acc_bytes = 0

                def flush_acc():
                    nonlocal acc, acc_bytes
                    if acc:
                        out.append(acc)
                        acc = {}
                        acc_bytes = 0

                while heap:
                    term, src = heapq.heappop(heap) # key, id_buf
                    t, postings = lists[src][idxs[src]]  # current term
                    merged = postings

                    # Advance this source
                    idxs[src] += 1
                    if idxs[src] < len(lists[src]):
                        nxt_term = lists[src][idxs[src]][0] # si ya no hay mas posting, al siguiente buffer
                        heapq.heappush(heap, (nxt_term, src))

                    while heap and heap[0][0] == term:
                        _, other = heapq.heappop(heap)
                        ot, opost = lists[other][idxs[other]]
                        merged = _merge_postings(merged, opost)
                        idxs[other] += 1
                        if idxs[other] < len(lists[other]):
                            nxt_term = lists[other][idxs[other]][0]
                            heapq.heappush(heap, (nxt_term, other))

                    rec_bytes = _estimate_bytes_for_record(term, merged)
                    if acc and acc_bytes + rec_bytes > BUCKET_LIMIT:
                        flush_acc()

                    if term in acc:
                        before = acc[term]
                        acc[term] = _merge_postings(before, merged)
                        new_bytes = _estimate_bytes_for_record(term, acc[term])
                        if acc and acc_bytes - _estimate_bytes_for_record(term, before) + new_bytes > BUCKET_LIMIT:
                            flush_acc()
                            acc[term] = merged
                            acc_bytes = _estimate_bytes_for_record(term, merged)
                    else:
                        acc[term] = merged
                        acc_bytes += rec_bytes

                    if acc_bytes > BUCKET_LIMIT:
                        flush_acc()
                        acc[term] = merged
                        acc_bytes = rec_bytes
                        if acc_bytes > BUCKET_LIMIT:
                            docs = sorted(merged.items())
                            chunk: Posting = {}
                            chunk_bytes = 0
                            for d_id, freq in docs:
                                inc = _estimate_bytes_for_record(term, {d_id: freq})
                                if chunk and chunk_bytes + inc > BUCKET_LIMIT:
                                    out.append({term: dict(chunk)})
                                    chunk.clear()
                                    chunk_bytes = 0
                                chunk[d_id] = freq
                                chunk_bytes += inc
                            if chunk:
                                out.append({term: dict(chunk)})
                            acc.clear()
                            acc_bytes = 0

                flush_acc()

            os.remove(current_name)
            os.rename(tmp_name, current_name)
            active_file = InvertedFile(current_name)
            self.file = active_file
            round_no += 1

    def _get_by_word(self, w: str) -> Tuple[Posting, int]:
        n = self.file._read_header()
        result: Posting = {}

        for i in range(n):
            b = self.file.read(i)
            postings = b.get(w)
            if postings:
                result = _merge_postings(result, postings)

        return result, len(result)

    def search(self, query: str, limit: int = 10) -> List[Tuple[str, float]]:
        query_tf = bow(query)
        total_docs = self.docfile._read_header() or 1

        filtered: List[Tuple[str, int]] = []           # (term, tf_q)
        postings_list: List[Tuple[Posting, int]] = []  # (postings, df)

        for term, tf in query_tf.items():
            postings, df = self._get_by_word(term)
            if df > 0:
                filtered.append((term, tf))
                postings_list.append((postings, df))

        if not postings_list:
            return []

        # query weights (smooth IDF)
        q_weights: Dict[str, float] = {}
        for (term, tf), (_, df) in zip(filtered, postings_list):
            idf = math.log((total_docs + 1) / (df + 1)) + 1.0
            q_weights[term] = tf * idf

        q_norm = math.sqrt(sum(w * w for w in q_weights.values())) or 1.0

        # accumulate doc scores
        scores: Dict[str, Dict[str, float]] = {}
        for (term, _tfq), (postings, df) in zip(filtered, postings_list):
            idf = math.log((total_docs + 1) / (df + 1)) + 1.0
            for doc_id, tf_d in postings.items():
                tfidf_d = tf_d * idf
                s = scores.setdefault(doc_id, {"dot": 0.0, "norm_sq": 0.0})
                s["dot"] += tfidf_d * q_weights[term]
                s["norm_sq"] += tfidf_d * tfidf_d

        results: List[Tuple[str, float]] = []
        for doc_id, s in scores.items():
            d_norm = math.sqrt(s["norm_sq"]) or 1.0
            sim = s["dot"] / (q_norm * d_norm)
            results.append((doc_id, sim))

        # ordenar: primero por score descendente, luego por doc_id ascendente
        results.sort(key=lambda x: (-x[1], x[0]))

        return results[:limit]

