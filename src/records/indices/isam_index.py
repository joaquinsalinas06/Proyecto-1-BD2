from typing import List, Dict, Any
from .base_index import BaseIndex

class ISAMIndex(BaseIndex):
    def __init__(self, column_name: str, filename: str = None, block_factor: int = 4):
        super().__init__(column_name, filename)
        self.block_factor = block_factor

    def search(self, key: Any) -> List[Dict[str, Any]]:
        return []

    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        return []

    def add(self, record: Dict[str, Any]) -> bool:
        return True

    def remove(self, key: Any) -> bool:
        return True