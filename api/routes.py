from fastapi import APIRouter, HTTPException
from api.models import QueryRequest, QueryResponse
from src.table_manager import TableManager

router = APIRouter()

db_manager = TableManager()

@router.post("/execute", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    query_preview = request.query[:100] + "..." if len(request.query) > 100 else request.query

    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query no puede estar vacía"
        )

    results = db_manager.sql(request.query)

    has_errors = any(result.get("error") for result in results)

    if has_errors:
        error_result = next(result for result in results if result.get("error"))
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": error_result["error"],
                "error_type": error_result.get("type", "unknown"),
                "query_preview": query_preview
            }
        )

    return QueryResponse(
        success=True,
        results=results,
        query_preview=query_preview
    )

