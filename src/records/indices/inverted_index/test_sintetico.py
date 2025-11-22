"""
Smoke test con dataset CSV - Mide tiempos de inserción y búsqueda
Ejecuta: python smoke_test_csv.py <ruta_csv> [num_filas]
Ejemplo: python smoke_test_csv.py spotify_songs.csv 1000
"""

import os
import sys
import csv
import tempfile
import shutil
import time

from .inverted_index import InvertedFile, InvertedIndex, BUCKET_LIMIT
from .document_file import DocumentFile
from .text_index import TextIndexer
from ...utils.text_type import TextType

def show_file_buckets(path: str):
    f = InvertedFile(path)
    n = f._read_header()
    print(f"\n[DEBUG] {path}: num_buckets={n}, BUCKET_LIMIT={BUCKET_LIMIT}\n")
    for i in range(n):
        b = f.read(i)
        print(f"Bucket {i}: {b}")


def leer_csv(ruta_csv, max_filas=None):
    """Lee el CSV y retorna lista de (track_id, lyrics)"""
    documentos = []
    
    with open(ruta_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader):
            if max_filas and i >= max_filas:
                break
            
            track_id = row.get('track_id', f'doc_{i}')
            lyrics = row.get('lyrics', '')
            
            # Solo indexar si hay letras
            if lyrics and lyrics.strip() and lyrics != 'NA':
                documentos.append((track_id, lyrics))
    
    return documentos


def main():
    if len(sys.argv) < 2:
        print("Uso: python smoke_test_csv.py <ruta_csv> [num_filas]")
        print("Ejemplo: python smoke_test_csv.py spotify_songs.csv 1000")
        sys.exit(1)
    
    ruta_csv = sys.argv[1]
    max_filas = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if not os.path.exists(ruta_csv):
        print(f"[ERROR] No existe el archivo: {ruta_csv}")
        sys.exit(1)
    
    # Leer CSV
    print(f"[INFO] Leyendo CSV: {ruta_csv}")
    print(f"[INFO] Límite de filas: {max_filas if max_filas else 'Sin límite'}")
    
    t_inicio_lectura = time.time()
    documentos = leer_csv(ruta_csv, max_filas)
    t_fin_lectura = time.time()
    
    print(f"[INFO] Documentos leídos: {len(documentos)}")
    print(f"[INFO] Tiempo lectura CSV: {t_fin_lectura - t_inicio_lectura:.3f}s\n")
    
    if not documentos:
        print("[ERROR] No se encontraron documentos con letras válidas")
        sys.exit(1)
    
    # Workspace temporal
    tmpdir = tempfile.mkdtemp(prefix="inv_csv_")
    try:
        inv_path = os.path.join(tmpdir, "inv.dat")
        doc_path = os.path.join(tmpdir, "inv_doc.dat")
        print(f"[INFO] Workspace: {tmpdir}\n")
        
        # ===== MEDICIÓN: INSERCIÓN =====
        print("=" * 60)
        print("FASE 1: INSERCIÓN DE DOCUMENTOS")
        print("=" * 60)
        
        indexer = TextIndexer(inv_path, doc_path)
        
        t_inicio_insert = time.time()
        for doc_id, lyrics in documentos:
            indexer.add_document(doc_id, lyrics)
        indexer.finalize()
        t_fin_insert = time.time()
        show_file_buckets(inv_path)
        
        tiempo_insert = t_fin_insert - t_inicio_insert
        print(f"\n[TIEMPO] Inserción total: {tiempo_insert:.3f}s")
        print(f"[TIEMPO] Promedio por doc: {tiempo_insert/len(documentos)*1000:.2f}ms")
        print(f"[TIEMPO] Docs/segundo: {len(documentos)/tiempo_insert:.2f}")
        
        
        print("[INFO] Buckets iniciales (antes de build_index):")
        
        # Build index


        print("\n[INFO] Construyendo índice (merge externo)...")
        t_inicio_build = time.time()
        inv = InvertedIndex(inv_path, docfile_path=doc_path)
        inv.build_index()
        t_fin_build = time.time()
        
        tiempo_build = t_fin_build - t_inicio_build
        print(f"[TIEMPO] Build index: {tiempo_build:.3f}s")
        
        # ===== MEDICIÓN: BÚSQUEDAS =====
        print("\n" + "=" * 60)
        print("FASE 2: BÚSQUEDAS")
        print("=" * 60)
        
        # Consultas de prueba (ajusta según tu dataset)
        consultas = [
            "love baby",
            "night dance",
            "heart soul",
            "feel alive",
            "music party",
            "dream forever"
        ]
        
        tiempos_busqueda = []
        
        for query in consultas:
            t_inicio_search = time.time()
            resultados = inv.search(query, limit=10)
            t_fin_search = time.time()
            
            tiempo_search = (t_fin_search - t_inicio_search) * 1000  # en ms
            tiempos_busqueda.append(tiempo_search)
            
            print(f"\n[BÚSQUEDA] '{query}'")
            print(f"  Tiempo: {tiempo_search:.2f}ms")
            print(f"  Resultados: {len(resultados)}")
            if resultados:
                top3 = resultados[:3]
                for doc_id, score in top3:
                    print(f"    - {doc_id}: {score:.4f}")
        
        # Estadísticas de búsqueda
        if tiempos_busqueda:
            print("\n" + "=" * 60)
            print("ESTADÍSTICAS DE BÚSQUEDA")
            print("=" * 60)
            print(f"Tiempo promedio: {sum(tiempos_busqueda)/len(tiempos_busqueda):.2f}ms")
            print(f"Tiempo mínimo: {min(tiempos_busqueda):.2f}ms")
            print(f"Tiempo máximo: {max(tiempos_busqueda):.2f}ms")
        
        # Resumen final
        print("\n" + "=" * 60)
        print("RESUMEN")
        print("=" * 60)
        print(f"Documentos indexados: {len(documentos)}")
        print(f"Tiempo inserción: {tiempo_insert:.3f}s")
        print(f"Tiempo build: {tiempo_build:.3f}s")
        print(f"Tiempo total indexación: {tiempo_insert + tiempo_build:.3f}s")
        print(f"Búsquedas realizadas: {len(consultas)}")
        if tiempos_busqueda:
            print(f"Tiempo promedio búsqueda: {sum(tiempos_busqueda)/len(tiempos_busqueda):.2f}ms")
        
        print(f"\n[OK] Test completado exitosamente")
        
    finally:
        # Limpieza (comenta para inspeccionar archivos)
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"\n[INFO] Limpieza: {tmpdir} eliminado")


if __name__ == "__main__":
    main()