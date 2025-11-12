# smoke_test_inverted_index.py
"""
Smoke test para el pipeline:
  TextIndexer.add_document -> flush a InvertedFile -> InvertedIndex.build_index -> search()
y verificación rápida de TextType.

Qué valida:
- Se crean buckets en disco y se pueden leer.
- El merge k-way produce términos ordenados y postings consolidados.
- search() devuelve algo razonable (cosine sobre TF-IDF).
- TextType escribe/lee correctamente.

Ejecuta:
  python smoke_test_inverted_index.py
"""

import os
import tempfile
import shutil

# --- ajusta estos imports a tu estructura real ---
from .inverted_index import InvertedFile, InvertedIndex  # si lo tienes en un paquete, ajusta ruta
from .inverted_index import BUCKET_LIMIT                  # para mostrar info de debug
from .document_file import DocumentFile                   # mismo: ajusta ruta si es necesario
from .text_index import TextIndexer                     # si tu TextIndexer está en otro archivo, ajusta
from ...utils.text_type import TextType                           # idem
# -----------------------------------------------------

def show_file_buckets(path: str):
    f = InvertedFile(path)
    n = f._read_header()
    print(f"\n[DEBUG] {path}: num_buckets={n}, BUCKET_LIMIT={BUCKET_LIMIT}\n")
    for i in range(n):
        b = f.read(i)
        print(f"Bucket {i}: {b}")

def main():
    # 1) Workspace temporal
    tmpdir = tempfile.mkdtemp(prefix="inv_smoke_")
    try:
        inv_path = os.path.join(tmpdir, "inv.dat")
        doc_path = os.path.join(tmpdir, "inv_doc.dat")   # Reusado por InvertedIndex
        print(f"[INFO] Workspace: {tmpdir}")

        # 2) Construir índice incrementalmente
        indexer = TextIndexer(inv_path, doc_path)

        # Documentos pequeños (usa tokens no-stopword para evitar filtros de NLTK)
        docs = {
            "d1": "cat dog dog tiger",
            "d2": "cat cat mouse",
            "d3": "mouse elephant",
            "d4": "tiger tiger cat",
        }

        for did, txt in docs.items():
            indexer.add_document(did, txt)
        indexer.finalize()

        print("[INFO] Buckets iniciales (antes de build_index):")
        show_file_buckets(inv_path)

        # 3) Merge externo y ordenación final
        inv = InvertedIndex(inv_path, docfile_path=doc_path)
        inv.build_index()

        print("\n[INFO] Buckets después de build_index (ordenados y fusionados):")
        show_file_buckets(inv_path)

        # 4) Probar _get_by_word() en términos clave
        for term in ["cat", "dog", "tiger", "mouse", "elephant", "nope"]:
            postings, df = inv._get_by_word(term)
            print(f"[CHECK] term='{term}' df={df} postings={postings}")

        # 5) Probar búsqueda ranking TF-IDF (cosine)
        for q in ["cat dog", "tiger", "mouse cat", "giraffe"]:
            res = inv.search(q, limit=5)
            print(f"[SEARCH] '{q}' -> {res}")

        # Quick sanity assertions (muy suaves, solo comprueban que hay señales razonables)
        # - 'cat dog' debería recuperar d1 y d2/d4 en top-3
        ranked = dict(inv.search("cat dog", limit=3))
        assert "d1" in ranked, "Esperaba d1 para 'cat dog'"
        # - 'tiger' debería incluir d4 (tiger tiger cat) y d1
        ranked_t = dict(inv.search("tiger", limit=3))
        assert any(d in ranked_t for d in ["d4", "d1"]), "Esperaba d4 o d1 para 'tiger'"
        # - consulta vacía no se prueba; consulta out-of-vocab regresa []
        assert inv.search("giraffe", limit=3) == [], "Consulta OOV debería dar []"

        print("\n[OK] InvertedIndex smoke test pasó checks básicos.")

        # 6) Smoke de TextType
        tpath = os.path.join(tmpdir, "columna_texto")
        tt = TextType(tpath)
        pos1, len1 = tt.write("hola mundo")
        pos2, len2 = tt.write("texto con UTF-8: ñ, á, ü")
        back1 = tt.read(pos1, len1)
        back2 = tt.read(pos2, len2)
        all_rows = tt.read_all()

        print(f"\n[TEXTTYPE] pos/len 1=({pos1},{len1}) -> '{back1}'")
        print(f"[TEXTTYPE] pos/len 2=({pos2},{len2}) -> '{back2}'")
        print(f"[TEXTTYPE] read_all() -> {all_rows}")

        assert back1 == "hola mundo"
        assert "ñ" in back2 and "á" in back2 and "ü" in back2
        assert len(all_rows) >= 2

        print("[OK] TextType smoke test pasó checks básicos.")

    finally:
        # Limpieza (comenta esta línea si quieres inspeccionar los archivos)
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"\n[INFO] Limpieza: {tmpdir} eliminado.")

if __name__ == "__main__":
    main()
