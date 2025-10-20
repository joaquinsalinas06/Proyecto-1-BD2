from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)

class QueryResponse(BaseModel):
    success: bool = True
    results: Optional[List[Dict[str, Any]]] = None
    data: Optional[List[Dict[str, Any]]] = None
    message: Optional[str] = None
    query_preview: str
    query_type: str
    execution_time_ms: Optional[float] = None
    affected_rows: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class ColumnInfo(BaseModel):
    name: str
    type: str
    indexed: bool
    indexType: Optional[str] = None
    primaryKey: bool

class TableInfo(BaseModel):
    name: str
    columns: List[ColumnInfo]
    row_count: int
    indexes: List[str]

class TableListResponse(BaseModel):
    tables: List[TableInfo]

class TableDetailsResponse(BaseModel):
    name: str
    description: str
    columns: List[ColumnInfo]
    data: List[Dict[str, Any]]

class QueryHistoryItem(BaseModel):
    query: str
    timestamp: str
    is_active: bool = False
    execution_time_ms: Optional[float] = None
    success: bool = True

class QueryHistoryResponse(BaseModel):
    history: List[QueryHistoryItem]