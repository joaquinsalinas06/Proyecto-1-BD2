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
        index_file = (
            self.filename.replace(".dat", "")
            if self.filename
            else f"{column_name}_rtree"
        )
        self.index_file = index_file

        # Create directory if it doesn't exist
        directory = os.path.dirname(self.index_file)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        if os.path.exists(f"{index_file}.dat") and os.path.exists(f"{index_file}.idx"):
            try:
                self.rtree_index = index.Index(index_file)
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
        """Calculate Euclidean distance between two points"""
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

        # Create search box (MBR) around query point
        min_coords = []
        max_coords = []
        for coord in point:
            min_coords.append(coord - radius)
            max_coords.append(coord + radius)
        mbr = tuple(min_coords) + tuple(max_coords)

        # Get candidates from box intersection, then filter by actual distance
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

    def remove(self, key: Any) -> bool:
        if not isinstance(key, (list, tuple)) or len(key) != self.dimensions:
            return False
        mbr = tuple(key) + tuple(key)
        removed = False
        for item in self.rtree_index.intersection(mbr, objects=True):
            stored_point = item.object
            if stored_point and tuple(stored_point) == tuple(key):
                self.rtree_index.delete(int(item.id), mbr)
                self._record_count -= 1
                removed = True
        return removed

    def getAllRecords(self) -> List[Dict[str, Any]]:
        """Returns all records stored in the R-tree index"""
        all_records = []
        pk_name = self.primary_key_column
        bounds = self.rtree_index.bounds
        if bounds:
            for pk_value in self.rtree_index.intersection(bounds):
                all_records.append({pk_name: pk_value})
        return all_records

    def clear_all(self) -> int:
        """Clears all records from the R-tree index"""
        old_count = self._record_count

        # Delete the index files
        for ext in [".dat", ".idx"]:
            filepath = f"{self.index_file}{ext}"
            if os.path.exists(filepath):
                os.remove(filepath)

        # Recreate empty index
        p = index.Property()
        p.dimension = self.dimensions
        p.leaf_capacity = self.max_entries
        p.fill_factor = 0.7
        self.rtree_index = index.Index(self.index_file, properties=p)
        self._record_count = 0

        return old_count