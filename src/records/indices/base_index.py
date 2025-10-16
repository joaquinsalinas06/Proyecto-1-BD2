from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
#from ...parser.ast import IndexType
from parser.ast import IndexType   # <-- ABSOLUTO



class BaseIndex(ABC):
    def __init__(self, column_name: str, filename: str = None, is_primary: bool = False, primary_key_column: str = None):
        self.column_name = column_name
        self.filename = filename or f"{column_name}_index.dat"
        self.is_primary = is_primary
        self.primary_key_column = primary_key_column

    @abstractmethod
    def search(self, key: Any) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def rangeSearch(self, begin_key: Any, end_key: Any,
                   begin_inclusive: bool = True, end_inclusive: bool = True) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def add(self, record: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def remove(self, key: Any) -> bool:
        pass

    @abstractmethod
    def getAllRecords(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def clear_all(self) -> int:
        pass


class SpatialIndex(BaseIndex):
    @abstractmethod
    def rangeSearch(self, point: Tuple[float, float], radius: float) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def knnSearch(self, point: Tuple[float, float], k: int) -> List[Dict[str, Any]]:
        pass


def create_index(index_type: IndexType, column_name: str, filename: str = None,
                is_primary: bool = False, primary_key_column: str = None, table_schema=None) -> BaseIndex:

    if index_type == IndexType.SEQ:
        from .sequential_file import SequentialFileIndex
        if not table_schema:
            raise ValueError("SequentialFileIndex requires table_schema")
        return SequentialFileIndex(column_name, table_schema, filename, is_primary, primary_key_column)

    elif index_type == IndexType.ISAM:
        from .isam_index import ISAMIndex
        return ISAMIndex(column_name, filename, is_primary, primary_key_column)

    elif index_type == IndexType.BTREE:
        from .btree_index import BTreeIndex
        return BTreeIndex(column_name, filename, is_primary, primary_key_column)

    elif index_type == IndexType.HASH:
        from .extendible_hash import ExtendibleHashIndex
        return ExtendibleHashIndex(column_name, filename, is_primary, primary_key_column)

    elif index_type == IndexType.RTREE:
        from .rtree_index import RTreeIndex
        #Esto es por si no definieron dimensiones en el schema, por defecto 2
        dimensiones = 2
        if table_schema:
            for col in table_schema:
                if col.name == column_name and col.array_dimensions:
                    dimensiones = col.array_dimensions
                    break
        return RTreeIndex(column_name, filename, is_primary, primary_key_column, dimensions=dimensiones)

    else:
        raise ValueError(f"Tipo de índice no soportado: {index_type}")
