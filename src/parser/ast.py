from dataclasses import dataclass
from typing import List, Optional, Union, Any
from enum import Enum


class DataType(Enum):
    INT = "INT"
    BIGINT = "BIGINT"
    FLOAT = "FLOAT"
    VARCHAR = "VARCHAR"
    DATE = "DATE"
    ARRAY = "ARRAY"


class IndexType(Enum):
    SEQ = "SEQ"
    BTREE = "BTREE"
    HASH = "HASH"
    ISAM = "ISAM"
    RTREE = "RTREE"


class CompOp(Enum):
    EQUALS = "="
    NOT_EQUALS = "!="
    LESS_THAN = "<"
    LESS_EQUALS = "<="
    GREATER_THAN = ">"
    GREATER_EQUALS = ">="


class LogicOp(Enum):
    AND = "AND"
    OR = "OR"


@dataclass
class ColumnDef:
    name: str
    data_type: DataType
    size: Optional[int] = None 
    element_type: Optional[DataType] = None
    is_key: bool = False
    index_type: Optional[IndexType] = None
    array_dimensions: Optional[int] = None


@dataclass
class Value:
    value: Any
    type: DataType

@dataclass
class CompCond:
    column: str
    operator: CompOp
    value: Value


@dataclass
class BetweenCond:
    column: str
    start_value: Value
    end_value: Value


@dataclass
class SpatialInCond:
    column: str
    point: tuple  # N-dimensional coordinates
    radius: float


@dataclass
class SpatialKNNCond:
    column: str
    point: tuple  # N-dimensional coordinates
    k: int


@dataclass
class LogicCond:
    left: 'Condition'
    operator: LogicOp
    right: 'Condition'


# Defniimos el tipo Condition como una unión de todas las condiciones posibles para facilitar su uso
Condition = Union[
    CompCond,
    BetweenCond,
    SpatialInCond,
    SpatialKNNCond,
    LogicCond
]

@dataclass
class CreateTableStmt:
    table_name: str
    columns: List[ColumnDef]


@dataclass
class IndexSpec:
    index_type: IndexType
    column_name: str
    is_primary: bool = False

@dataclass
class CreateTableFileStmt:
    table_name: str
    file_path: str
    indexes: List[IndexSpec]  # Lista de especificaciones de índices


@dataclass
class SelectStmt:
    table_name: str
    columns: List[str]
    where_condition: Optional[Condition] = None
    order_by: Optional[str] = None
    order_desc: bool = False
    limit: Optional[int] = None


@dataclass
class InsertStmt:
    table_name: str
    values: List[Value]


@dataclass
class DeleteStmt:
    table_name: str
    where_condition: Optional[Condition] = None

# Definimos el tipo Statement como una unión de todas las sentencias posibles para facilitar su uso
Statement = Union[
    CreateTableStmt,
    CreateTableFileStmt,
    SelectStmt,
    InsertStmt,
    DeleteStmt
]


