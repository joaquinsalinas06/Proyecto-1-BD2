
import csv
import shutil
from pathlib import Path

def print_io_stats(tm, table_name, operation_name, num_operations=1):
    stats = tm.get_io_stats(table_name)
    
    if not stats:
        return
    
    total_io = stats.get('disk_reads', 0) + stats.get('disk_writes', 0)
    
    print(f"   I/O - {operation_name}:")
    print(f"      • Lecturas: {stats.get('disk_reads', 0)}")
    print(f"      • Escrituras: {stats.get('disk_writes', 0)}")
    print(f"      • Total I/O: {total_io}")
    
    if num_operations > 1:
        avg_reads = stats.get('disk_reads', 0) / num_operations
        avg_writes = stats.get('disk_writes', 0) / num_operations
        avg_total = total_io / num_operations
        print(f"      • Promedio por operación: {avg_total:.2f} I/O ({avg_reads:.2f} reads, {avg_writes:.2f} writes)")
    
    if 'page_reads' in stats:
        print(f"      • Page reads: {stats['page_reads']}, Page writes: {stats['page_writes']}")
    if 'overflow_reads' in stats:
        print(f"      • Overflow reads: {stats['overflow_reads']}, Overflow writes: {stats['overflow_writes']}")
    if 'node_reads' in stats:
        print(f"      • Node reads: {stats['node_reads']}, Node writes: {stats['node_writes']}")


def capture_io_stats(tm, table_name):
    """Captura estadísticas de I/O y agrega campos calculados para compatibilidad"""
    stats = tm.get_io_stats(table_name)
    
    if stats:
        # Agregar total_io calculado para compatibilidad con benchmarks
        stats['total_io'] = stats.get('disk_reads', 0) + stats.get('disk_writes', 0)
        # Mantener 'reads' y 'writes' como aliases para compatibilidad
        stats['reads'] = stats.get('disk_reads', 0)
        stats['writes'] = stats.get('disk_writes', 0)
    
    return stats
