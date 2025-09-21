from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from ...parser.ast import IndexType


class BaseIndex(ABC):
    def __init__(self, column_name: str, filename: str = None):
        self.column_name = column_name
        self.filename = filename or f"{column_name}_index.dat"

    @abstractmethod
    def search(self, key: Any) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def add(self, record: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def remove(self, key: Any) -> bool:
        pass


class SpatialIndex(BaseIndex):
    @abstractmethod
    def rangeSearch(self, point: Tuple[float, float], radius: float) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def knnSearch(self, point: Tuple[float, float], k: int) -> List[Dict[str, Any]]:
        pass


def create_index(index_type: IndexType, column_name: str, filename: str = None) -> BaseIndex:
    if index_type == IndexType.SEQ:
        from .sequential_file import SequentialFileIndex
        return SequentialFileIndex(column_name, filename)

    elif index_type == IndexType.ISAM:
        from .isam_index import ISAMIndex
        return ISAMIndex(column_name, filename)

    elif index_type == IndexType.BTREE:
        from .btree_index import BTreeIndex
        return BTreeIndex(column_name, filename)

    elif index_type == IndexType.HASH:
        from .extendible_hash import ExtendibleHashIndex
        return ExtendibleHashIndex(column_name, filename)

    elif index_type == IndexType.RTREE:
        from .rtree_index import RTreeIndex
        return RTreeIndex(column_name, filename)

    else:
        raise ValueError(f"Tipo de índice no soportado: {index_type}")
