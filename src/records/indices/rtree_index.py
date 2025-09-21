from typing import List, Dict, Any, Tuple
from .base_index import SpatialIndex

class RTreeIndex(SpatialIndex):
    def __init__(self, column_name: str, filename: str = None, max_entries: int = 4):
        super().__init__(column_name, filename)
        self.max_entries = max_entries

    def search(self, key: Any) -> List[Dict[str, Any]]:
        return []

    def rangeSearch(self, point: Tuple[float, float], radius: float) -> List[Dict[str, Any]]:
        return []

    def knnSearch(self, point: Tuple[float, float], k: int) -> List[Dict[str, Any]]:
        return []

    def add(self, record: Dict[str, Any]) -> bool:
        return True

    def remove(self, key: Any) -> bool:
        return True