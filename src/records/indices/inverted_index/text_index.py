from inverted_index import InvertedFile, BType, BUCKET_LIMIT, _estimate_bytes_for_record
from document_file import DocumentFile
from utils.text_utils import bow  # bag of words: str -> Dict[str, int]

class TextIndexer:

    def __init__(self, index_path: str, doc_path: str) -> None:
        self.inverted = InvertedFile(index_path)
        self.docs = DocumentFile(doc_path)
        self._bucket: BType = {}
        self._bucket_bytes = 0  # approximate size of serialized bucket

    def _flush(self) -> None:
        if self._bucket:
            self.inverted.append(self._bucket) # escribir en memoria
            self._bucket.clear()
            self._bucket_bytes = 0

    def _maybe_flush_after_add(self, term: str, doc_id: str, freq: int) -> str | None:
    
        inc = _estimate_bytes_for_record(term, {doc_id: freq})

        if self._bucket_bytes == 0 and inc > BUCKET_LIMIT:
            try:
                self.inverted.append({term: {doc_id: freq}})
                return "direct"
            except ValueError:
                raise ValueError(
                    f"La entrada mínima para term='{term}' y doc='{doc_id}' "
                    f"no cabe en un bucket de {BUCKET_LIMIT} bytes. "
                    "Aumenta BUCKET_LIMIT o cambia el formato de almacenamiento."
                )

        if self._bucket_bytes and self._bucket_bytes + inc > BUCKET_LIMIT:
            self._flush()
            return "flushed"

        return None

    def add_document(self, doc_id: str, text: str) -> None:
        """
            convierte el texto en una bolsa de palabras (bow),
            agrega la información al índice invertido,
            y registra el documento en el DocumentFile.    
        """
        bow_ = bow(text)
        self.docs.append(doc_id, len(bow_)) # para facil accesso futuro

        for term, freq in bow_.items():
            action = self._maybe_flush_after_add(term, doc_id, freq)
            if action == "direct":
                # ya se escribió como bucket propio
                continue
            postings = self._bucket.setdefault(term, {})
            prev = postings.get(doc_id, 0)
            postings[doc_id] = prev + freq

            self._bucket_bytes += _estimate_bytes_for_record(term, {doc_id: postings[doc_id]})

            if self._bucket_bytes > BUCKET_LIMIT:
                # rollback seguro
                if postings[doc_id] == freq:
                    postings.pop(doc_id, None)
                else:
                    postings[doc_id] -= freq
                if not postings:
                    self._bucket.pop(term, None)
                self._flush()
                # reintentar una vez (debería caber ahora)
                postings = self._bucket.setdefault(term, {})
                postings[doc_id] = postings.get(doc_id, 0) + freq
                self._bucket_bytes += _estimate_bytes_for_record(term, {doc_id: postings[doc_id]})

    def finalize(self) -> None:
        self._flush()
