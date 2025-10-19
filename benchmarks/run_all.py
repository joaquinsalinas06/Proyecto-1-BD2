import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from benchmarks import benchmark_01_airbnb_sequential
from benchmarks import benchmark_02_airbnb_isam
from benchmarks import benchmark_03_airbnb_btree
from benchmarks import benchmark_01_games_sequential
from benchmarks import benchmark_02_games_isam
from benchmarks import benchmark_03_games_btree

def run_all():
    print("\n" + "="*80)
    print("Benchmarks de Índices - Airbnb y Games")
    print("="*80)
    
    print("\n" + "="*80)
    print("Dataset: Airbnb")
    print("="*80)
    airbnb_seq = benchmark_01_airbnb_sequential.run_benchmark()
    airbnb_isam = benchmark_02_airbnb_isam.run_benchmark()
    airbnb_btree = benchmark_03_airbnb_btree.run_benchmark()
    
    print("\n" + "="*80)
    print("Dataset: Games")
    print("="*80)
    games_seq = benchmark_01_games_sequential.run_benchmark()
    games_isam = benchmark_02_games_isam.run_benchmark()
    games_btree = benchmark_03_games_btree.run_benchmark()
    
    print("\n" + "="*80)
    print("Comparación Final - Airbnb")
    print("="*80)
    print(f"{'Índice':<15} {'1K Carga':<12} {'1K PK':<10} {'10K Carga':<12} {'10K PK':<10} {'100K Carga':<12} {'100K PK':<10}")
    print("─"*80)
    print(f"{'Sequential':<15} {airbnb_seq[0]['bulk']:<12.2f} {airbnb_seq[0]['pk']:<10.2f} {airbnb_seq[1]['bulk']:<12.2f} {airbnb_seq[1]['pk']:<10.2f} {airbnb_seq[2]['bulk']:<12.2f} {airbnb_seq[2]['pk']:<10.2f}")
    print(f"{'ISAM':<15} {airbnb_isam[0]['bulk']:<12.2f} {airbnb_isam[0]['pk']:<10.2f} {airbnb_isam[1]['bulk']:<12.2f} {airbnb_isam[1]['pk']:<10.2f} {airbnb_isam[2]['bulk']:<12.2f} {airbnb_isam[2]['pk']:<10.2f}")
    print(f"{'B+Tree':<15} {airbnb_btree[0]['bulk']:<12.2f} {airbnb_btree[0]['pk']:<10.2f} {airbnb_btree[1]['bulk']:<12.2f} {airbnb_btree[1]['pk']:<10.2f} {airbnb_btree[2]['bulk']:<12.2f} {airbnb_btree[2]['pk']:<10.2f}")
    
    print("\n" + "="*80)
    print("Comparación Final - Games")
    print("="*80)
    print(f"{'Índice':<15} {'1K Carga':<12} {'1K PK':<10} {'10K Carga':<12} {'10K PK':<10} {'100K Carga':<12} {'100K PK':<10}")
    print("─"*80)
    print(f"{'Sequential':<15} {games_seq[0]['bulk']:<12.2f} {games_seq[0]['pk']:<10.2f} {games_seq[1]['bulk']:<12.2f} {games_seq[1]['pk']:<10.2f} {games_seq[2]['bulk']:<12.2f} {games_seq[2]['pk']:<10.2f}")
    print(f"{'ISAM':<15} {games_isam[0]['bulk']:<12.2f} {games_isam[0]['pk']:<10.2f} {games_isam[1]['bulk']:<12.2f} {games_isam[1]['pk']:<10.2f} {games_isam[2]['bulk']:<12.2f} {games_isam[2]['pk']:<10.2f}")
    print(f"{'B+Tree':<15} {games_btree[0]['bulk']:<12.2f} {games_btree[0]['pk']:<10.2f} {games_btree[1]['bulk']:<12.2f} {games_btree[1]['pk']:<10.2f} {games_btree[2]['bulk']:<12.2f} {games_btree[2]['pk']:<10.2f}")
    print("="*80)

if __name__ == "__main__":
    run_all()
