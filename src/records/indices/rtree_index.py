from typing import List, Dict, Any, Tuple
from rtree import index
import os
from .base_index import SpatialIndex

class RTreeIndex(SpatialIndex):
    def __init__(
        self,
        column_name: str,
        filename: str = None,
        is_primary: bool = False,
        primary_key_column: str = None,
        max_entries: int = 50,
        dimensions: int = 2,
    ):
        super().__init__(column_name, filename, is_primary, primary_key_column)
        self.dimensions = dimensions
        self.max_entries = max_entries
        self._record_count = 0
        base_filename = self.filename.replace('.dat', '')
        self.index_file = base_filename

        directory = os.path.dirname(self.index_file)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        if os.path.exists(f"{self.index_file}.dat") and os.path.exists(f"{self.index_file}.idx"):
            try:
                self.rtree_index = index.Index(self.index_file)
                self._record_count = len(list(self.rtree_index.intersection(self.rtree_index.bounds)))
            except Exception as e:
                p = index.Property()
                p.dimension = self.dimensions
                p.leaf_capacity = self.max_entries
                p.fill_factor = 0.7
                self.rtree_index = index.Index(self.index_file, properties=p)
        else:
            p = index.Property()
            p.dimension = self.dimensions
            p.leaf_capacity = self.max_entries
            p.fill_factor = 0.7
            self.rtree_index = index.Index(self.index_file, properties=p)

    def _euclidean_distance(self, point1: Tuple, point2: Tuple) -> float:
        squared_sum = 0
        for c1, c2 in zip(point1, point2):
            squared_sum += (c1 - c2)**2
        return squared_sum**0.5

    def search(self, key: Any) -> List[Dict[str, Any]]:
        if not isinstance(key, (list, tuple)) or len(key) != self.dimensions:
            return []

        epsilon = 1e-9
        min_coords = []
        max_coords = []
        for coord in key:
            min_coords.append(coord - epsilon)
            max_coords.append(coord + epsilon)
        mbr = tuple(min_coords) + tuple(max_coords)

        results = []
        pk_name = self.primary_key_column
        for item in self.rtree_index.intersection(mbr, objects=True):
            stored_point = item.object
            if stored_point:
                is_exact_match = True
                for k, s in zip(key, stored_point):
                    if abs(k - s) >= epsilon:
                        is_exact_match = False
                        break
                if is_exact_match:
                    results.append({pk_name: item.id})
        return results

    def rangeSearch(
        self, point: Tuple[float, ...], radius: float
    ) -> List[Dict[str, Any]]:
        if not isinstance(point, (list, tuple)) or len(point) != self.dimensions:
            return []

        min_coords = []
        max_coords = []
        for coord in point:
            min_coords.append(coord - radius)
            max_coords.append(coord + radius)
        mbr = tuple(min_coords) + tuple(max_coords)

        results = []
        pk_name = self.primary_key_column
        for item in self.rtree_index.intersection(mbr, objects=True):
            stored_point = item.object
            if stored_point:
                distance = self._euclidean_distance(point, stored_point)
                if distance <= radius:
                    results.append({pk_name: item.id})
        return results

    def knnSearch(self, point: Tuple[float, ...], k: int) -> List[Dict[str, Any]]:
        if not isinstance(point, (list, tuple)) or len(point) != self.dimensions:
            return []

        results = []
        pk_name = self.primary_key_column
        for pk_value in self.rtree_index.nearest(point, k):
            results.append({pk_name: pk_value})
        return results

    def add(self, record: Dict[str, Any]) -> bool:
        if self.column_name not in record or self.primary_key_column not in record:
            return False
        point = record[self.column_name]
        pk_value = record[self.primary_key_column]
        if not isinstance(point, (list, tuple)) or len(point) != self.dimensions:
            return False
        mbr = tuple(point) + tuple(point)
        self.rtree_index.insert(int(pk_value), mbr, obj=tuple(point))
        self._record_count += 1
        return True

    def bulk_load(self, records: List[Dict[str, Any]]) -> int:
        loaded = 0
        valid_entries = []

        # Obtenemos en una lista todas las llaves primarias y sus puntos asociados
        for record in records:
            if self.column_name not in record or self.primary_key_column not in record:
                continue
            
            point = record[self.column_name]
            pk_value = record[self.primary_key_column]
            
            if not isinstance(point, (list, tuple)) or len(point) != self.dimensions:
                continue
            
            try:
                pk_int = int(pk_value)
                point_tuple = tuple(point)
                mbr = point_tuple + point_tuple
                valid_entries.append((pk_int, mbr, point_tuple))
            except (ValueError, TypeError):
                continue

        # Este generador provee los datos en el formato esperado por rtree para carga masiva
        def data_generator():
            for pk_int, mbr, point_tuple in valid_entries:
                yield (pk_int, mbr, point_tuple)

        if hasattr(self, 'rtree_index'):
            try:
                self.rtree_index.close()
            except:
                pass

        for ext in [".dat", ".idx"]:
            filepath = f"{self.index_file}{ext}"
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass

        p = index.Property()
        p.dimension = self.dimensions
        p.leaf_capacity = self.max_entries
        p.fill_factor = 0.7
        
        #Aprovechamos la carga masiva de la libreria del rtree para insertar todos los puntos de una vez
        self.rtree_index = index.Index(self.index_file, data_generator(), properties=p)
        
        loaded = len(valid_entries)
        self._record_count = loaded

        return loaded

    def remove(self, key: Any, primary_key: Any = None) -> bool:
        if not isinstance(key, (list, tuple)) or len(key) != self.dimensions:
            return False
        mbr = tuple(key) + tuple(key)
        if primary_key is not None:
            try:
                self.rtree_index.delete(int(primary_key), mbr)
                self._record_count -= 1
                return True
            except Exception:
                return False
        removed = False
        for item in self.rtree_index.intersection(mbr, objects=True):
            stored_point = item.object
            if stored_point and tuple(stored_point) == tuple(key):
                self.rtree_index.delete(int(item.id), mbr)
                self._record_count -= 1
                removed = True
        return removed

    def getAllRecords(self) -> List[Dict[str, Any]]:
        all_records = []
        pk_name = self.primary_key_column
        bounds = self.rtree_index.bounds
        if bounds:
            for pk_value in self.rtree_index.intersection(bounds):
                all_records.append({pk_name: pk_value})
        return all_records

    def clear_all(self) -> int:
        old_count = self._record_count
        for ext in [".dat", ".idx"]:
            filepath = f"{self.index_file}{ext}"
            if os.path.exists(filepath):
                os.remove(filepath)

        p = index.Property()
        p.dimension = self.dimensions
        p.leaf_capacity = self.max_entries
        p.fill_factor = 0.7
        self.rtree_index = index.Index(self.index_file, properties=p)
        self._record_count = 0

        return old_count