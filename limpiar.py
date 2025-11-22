import csv
import re

def clean_and_filter_csv(input_file, output_file):
    """
    Limpia el CSV y extrae SOLO las columnas necesarias para PostgreSQL
    """
    
    # Columnas que queremos del CSV original
    columns_to_keep = [
        'track_id',           # 0
        'track_name',         # 1
        'track_artist',       # 2
        'lyrics',             # 3
        'track_popularity',   # 4
        'track_album_name',   # 6
        'playlist_genre',     # 10
        'playlist_subgenre',  # 11
        'language'            # 24
    ]
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        
        # Verificar que existan las columnas
        missing = set(columns_to_keep) - set(reader.fieldnames)
        if missing:
            print(f"⚠️  Columnas faltantes: {missing}")
            return
        
        cleaned_rows = []
        errors = []
        
        for i, row in enumerate(reader, start=2):
            try:
                cleaned_row = {}
                
                for col in columns_to_keep:
                    cell = row[col] or ''  # Manejar valores None
                    
                    # Limpieza básica
                    cell = ''.join(char for char in cell if char.isprintable() or char in [' ', '\t'])
                    cell = cell.replace('\n', ' ').replace('\r', ' ')
                    cell = cell.replace(',', ' ')  # Eliminar comas internas
                    cell = cell.replace('"', ' ')  # Eliminar comillas
                    cell = cell.replace("'", ' ')  # Eliminar apóstrofes
                    
                    # Mantener solo caracteres seguros
                    cell = re.sub(r"[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s]", " ", cell)
                    cell = re.sub(r"\s+", " ", cell).strip()
                    
                    # Limitar longitud (opcional, para evitar textos muy largos)
                    if col == 'lyrics':
                        cell = cell[:5000]  # Limitar lyrics a 5000 caracteres
                    else:
                        cell = cell[:500]   # Otras columnas a 500 caracteres
                    
                    cleaned_row[col] = cell
                
                cleaned_rows.append(cleaned_row)
                
            except Exception as e:
                errors.append((i, str(e)))
        
        # Escribir CSV limpio
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            # Nota: NO incluimos 'created_at' porque PostgreSQL lo generará automáticamente
            writer = csv.DictWriter(f, fieldnames=columns_to_keep, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(cleaned_rows)
    
    print(f"\n{'='*60}")
    print(f"✓ CSV limpio guardado en: {output_file}")
    print(f"  Filas procesadas: {len(cleaned_rows)}")
    print(f"  Errores: {len(errors)}")
    
    if errors:
        print(f"\n⚠️  Primeros errores:")
        for line, error in errors[:3]:
            print(f"  Línea {line}: {error}")
    
    # Verificar resultado
    with open(output_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        first_row = next(reader)
        print(f"\n📋 Verificación:")
        print(f"  Columnas: {len(header)} (esperadas: 9)")
        print(f"  Primera fila tiene {len(first_row)} valores")
        print(f"  Ejemplo: {first_row[0]}, {first_row[1]}, {first_row[2][:30]}...")


if __name__ == "__main__":
    input_file = "spotify_songs.csv"
    output_file = "spotify_songs_cleaned.csv"
    
    print("🧹 Limpiando y filtrando CSV...")
    print("="*60)
    
    try:
        clean_and_filter_csv(input_file, output_file)
        print("\n✅ ¡Listo! Ahora intenta el COPY nuevamente en PostgreSQL")
        
    except FileNotFoundError:
        print(f"❌ Error: No se encontró '{input_file}'")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()