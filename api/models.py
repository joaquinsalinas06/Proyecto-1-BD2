from typing import Dict, Any, List
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)

class QueryResponse(BaseModel):
    success: bool
    results: List[Dict[str, Any]]
    query_preview: str