"use client"

import { useState, useEffect } from "react"
import axios from "axios"
import { Sidebar } from "@/components/sidebar"
import { QueryEditor } from "@/components/query-editor"
import { ResultsSection } from "@/components/results-section"
import { TableDetails } from "@/components/table-details"

const API_BASE_URL = "http://localhost:8000"

export default function SQLEditor() {
  const [currentQuery, setCurrentQuery] = useState("")
  const [results, setResults] = useState<Record<string, any>[]>([])
  const [queryMetadata, setQueryMetadata] = useState<any>(null)
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<"queries" | "tables">("queries")
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tableDetailsData, setTableDetailsData] = useState<any>(null)
  const [loadingTableDetails, setLoadingTableDetails] = useState(false)
  const [tables, setTables] = useState<string[]>([])
  const [queryHistory, setQueryHistory] = useState<any[]>([])

  useEffect(() => {
    fetchTables()
    fetchHistory()
  }, [])

  const fetchTables = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/tables`)
      if (response.data.tables) {
        setTables(response.data.tables.map((t: any) => t.name))
      }
    } catch (err) {
      console.error("Error fetching tables:", err)
    }
  }

  const fetchHistory = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/history`)
      if (response.data.history) {
        setQueryHistory(response.data.history.map((h: any) => ({
          query: h.query,
          timestamp: h.timestamp,
          isActive: false
        })))
      }
    } catch (err) {
      console.error("Error fetching history:", err)
    }
  }

  const handleQueryChange = (query: string) => {
    setCurrentQuery(query)
  }

  const handleExecuteQuery = async () => {
    if (!currentQuery.trim()) {
      setError("La consulta no puede estar vacía")
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await axios.post(`${API_BASE_URL}/execute`, {
        query: currentQuery.trim()
      })

      if (response.data.success) {
        // Limpiar error en caso de éxito
        setError(null)
        // Usar data para consultas SELECT, results para información general
        const queryData = response.data.data || []
        setResults(queryData)
        setQueryMetadata({
          message: response.data.message,
          queryType: response.data.query_type,
          executionTime: response.data.execution_time_ms,
          affectedRows: response.data.affected_rows,
          metadata: response.data.metadata
        })
        fetchHistory()
        fetchTables()
      } else {
        setError("Error al ejecutar la consulta")
      }
    } catch (err: any) {
      console.log("Error response:", err.response?.data); // Debug log
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail
        if (typeof detail === 'object' && detail.error) {
          setError(detail.error)
        } else if (typeof detail === 'string') {
          setError(detail)
        } else {
          setError("Error al ejecutar la consulta")
        }
      } else if (err.response?.status >= 400 && err.response?.status < 500) {
        // Error HTTP 4xx - problema con la consulta
        setError(err.response?.data?.message || "Error en la consulta SQL")
      } else if (err.code === 'ECONNREFUSED') {
        setError("El servidor de base de datos no está ejecutándose. Por favor inicie el servidor API en el puerto 8000.")
      } else {
        setError(err.message || "Ocurrió un error inesperado")
      }
      // Solo actualizar historial si realmente hubo un error
      if (err.response?.status >= 400) {
        fetchHistory()
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleHistoryItemClick = (query: string) => {
    setCurrentQuery(query)
  }

  const handleTableClick = async (tableName: string) => {
    setSelectedTable(tableName)
  }

  const fetchTableDetails = async (tableName: string) => {
    setLoadingTableDetails(true)
    try {
      const response = await axios.get(`${API_BASE_URL}/tables/${tableName}`)
      setTableDetailsData(response.data)
    } catch (err) {
      console.error("Error fetching table details:", err)
      setTableDetailsData({
        name: tableName,
        description: `Tabla '${tableName}'`,
        columns: [],
        data: []
      })
    } finally {
      setLoadingTableDetails(false)
    }
  }

  useEffect(() => {
    if (selectedTable) {
      fetchTableDetails(selectedTable)
    }
  }, [selectedTable])

  return (
    <div className="flex h-screen text-background" style={{ backgroundColor: "#101c22" }}>
      <Sidebar
        tables={tables}
        queryHistory={queryHistory}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onHistoryItemClick={handleHistoryItemClick}
        onTableClick={handleTableClick}
        selectedTable={selectedTable}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden relative">
          {/* Query Editor View */}
          <div
            className={`absolute inset-0 transition-all duration-300 ease-in-out ${
              selectedTable && tableDetailsData
                ? "opacity-0 -translate-x-full pointer-events-none"
                : "opacity-100 translate-x-0"
            }`}
          >
            <div className="h-full flex flex-col">
              <QueryEditor
                query={currentQuery}
                onQueryChange={handleQueryChange}
                onExecute={handleExecuteQuery}
                isLoading={isLoading}
              />
              <ResultsSection
                results={results}
                isLoading={isLoading}
                error={error}
                metadata={queryMetadata}
              />
            </div>
          </div>
          <div
            className={`absolute inset-0 transition-all duration-300 ease-in-out ${
              selectedTable && tableDetailsData
                ? "opacity-100 translate-x-0"
                : "opacity-0 translate-x-full pointer-events-none"
            }`}
          >
            {selectedTable && tableDetailsData && (
              <TableDetails
                table={tableDetailsData}
                onBackToQuery={() => setSelectedTable(null)}
              />
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
