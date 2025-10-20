from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import List
import time
from src.table_manager import TableManager
from api.models import (
    QueryRequest, QueryResponse, TableListResponse,
    TableDetailsResponse, QueryHistoryResponse, QueryHistoryItem
)

router = APIRouter()

tm = TableManager()

query_history: List[QueryHistoryItem] = []

# Se obtienen todas las tablas disponibles
@router.get("/tables", response_model=TableListResponse)
async def get_tables():
    try:
        tables_metadata = tm.get_all_tables_metadata()
        return TableListResponse(tables=tables_metadata)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener tablas: {str(e)}"
        )

# Se obtienen los detalles de una tabla específica
@router.get("/tables/{table_name}", response_model=TableDetailsResponse)
async def get_table_details(table_name: str, limit: int = 25):
    try:
        table_details = tm.get_table_details(table_name, preview_limit=limit)
        return TableDetailsResponse(**table_details)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener detalles de tabla: {str(e)}"
        )

#Mostrar el historial de consultas
@router.get("/history", response_model=QueryHistoryResponse)
async def get_query_history():
    return QueryHistoryResponse(history=query_history)

@router.post("/execute", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    query_preview = request.query[:100] + "..." if len(request.query) > 100 else request.query

    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query no puede estar vacía"
        )

    #Iniciamos una medicion de tiempo para ver el tiempo de ejecucion
    start_time = time.time()
    try:
        results = tm.sql(request.query)
    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000

        _add_to_history(request.query, execution_time_ms, success=False)

        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": str(e),
                "query_preview": query_preview
            }
        )
    execution_time_ms = (time.time() - start_time) * 1000

    has_errors = any(result.get("error") for result in results)

    if has_errors:
        error_result = next(result for result in results if result.get("error"))
        _add_to_history(request.query, execution_time_ms, success=False)
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": error_result["error"],
                "error_type": error_result.get("type", "unknown"),
                "query_preview": query_preview
            }
        )

    first_result = results[0] if results else {}
    query_type = first_result.get("type", "unknown")

    response_data = None
    response_message = None
    affected_rows = None
    metadata = {}

    # Construir la respuesta basada en el tipo de consulta, si es un select recuperar
    # los datos, si es insert/delete/crear tabla, devolver mensaje y filas afectadas
    if query_type == "select":
        response_data = first_result.get("data", [])
        affected_rows = first_result.get("rows_count", 0)
        metadata = {
            "table_name": first_result.get("table_name"),
            "rows_count": first_result.get("rows_count", 0)
        }
        response_message = f"{affected_rows} filas recuperadas"

    elif query_type in ["insert", "delete", "create_table", "create_table_from_file"]:
        response_message = first_result.get("message", "Operación completada")
        affected_rows = first_result.get("deleted_count", 1 if query_type == "insert" else 0)
        metadata = {
            "table_name": first_result.get("table_name"),
            "operation": query_type
        }

    _add_to_history(request.query, execution_time_ms, success=True)

    return QueryResponse(
        success=True,
        results=results,
        query_preview=query_preview,
        data=response_data,
        message=response_message,
        query_type=query_type,
        execution_time_ms=round(execution_time_ms, 2),
        affected_rows=affected_rows,
        metadata=metadata
    )

# Añade a la lista alguna accion o consulta realizada, que puede o no haber sido exitosa
def _add_to_history(query: str, execution_time_ms: float, success: bool = True):
    global query_history

    history_item = QueryHistoryItem(
        query=query,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        is_active=False,
        execution_time_ms=round(execution_time_ms, 2),
        success=success
    )

    query_history.insert(0, history_item)

    if len(query_history) > 50:
        query_history = query_history[:50]