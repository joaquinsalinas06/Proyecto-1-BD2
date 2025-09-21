from typing import List, Dict, Any
from .base_index import BaseIndex

class SequentialFileIndex(BaseIndex):
    def __init__(self, column_name: str, filename: str = None, k: int = 10):
        super().__init__(column_name, filename)
        self.k = k

    def search(self, key: Any) -> List[Dict[str, Any]]:
        return []

    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        return []

    def add(self, record: Dict[str, Any]) -> bool:
        return True

    def remove(self, key: Any) -> bool:
        return True 
