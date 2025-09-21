from typing import List, Dict, Any
from .base_index import BaseIndex

class ExtendibleHashIndex(BaseIndex):
    def __init__(self, column_name: str, filename: str = None, bucket_capacity: int = 4):
        super().__init__(column_name, filename)
        self.bucket_capacity = bucket_capacity
        self.global_depth = 1

    def search(self, key: Any) -> List[Dict[str, Any]]:
        return []

    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        raise NotImplementedError("Hash index no soporta range search - usar otros índices para consultas por rango")

    def add(self, record: Dict[str, Any]) -> bool:
        return True 
    
    def remove(self, key: Any) -> bool:
        return True
