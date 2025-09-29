"use client"

import { useState } from "react"
import axios from "axios"
import { Sidebar } from "@/components/sidebar"
import { QueryEditor } from "@/components/query-editor"
import { ResultsSection } from "@/components/results-section"
import { TableDetails } from "@/components/table-details"

export default function SQLEditor() {
  const [currentQuery, setCurrentQuery] = useState("")
  const [results, setResults] = useState<Record<string, any>[]>([])
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<"queries" | "tables">("queries")
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
      const response = await axios.post('http://localhost:8000/execute', {
        query: currentQuery.trim()
      })

      if (response.data.success) {
        setResults(response.data.results || [])
      } else {
        setError("Error al ejecutar la consulta")
      }
    } catch (err: any) {
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail
        if (typeof detail === 'object' && detail.error) {
          setError(detail.error)
        } else if (typeof detail === 'string') {
          setError(detail)
        } else {
          setError("Error al ejecutar la consulta")
        }
      } else if (err.code === 'ECONNREFUSED') {
        setError("El servidor de base de datos no está ejecutándose. Por favor inicie el servidor API en el puerto 8000.")
      } else {
        setError(err.message || "Ocurrió un error inesperado")
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleHistoryItemClick = (query: string) => {
    setCurrentQuery(query)
  }

  const handleTableClick = (tableName: string) => {
    setSelectedTable(tableName)
    setCurrentQuery(`SELECT * FROM ${tableName};`)
  }

  return (
    <div className="flex h-screen text-background" style={{ backgroundColor: "#101c22" }}>
      <Sidebar
        tables={[]}
        queryHistory={[]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onHistoryItemClick={handleHistoryItemClick}
        onTableClick={handleTableClick}
        selectedTable={selectedTable}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      <main className="flex-1 flex flex-col overflow-hidden">
        {selectedTable ? (
          <TableDetails table={{
            name: selectedTable,
            description: `Esquema de tabla y vista previa de datos para la tabla '${selectedTable}'.`,
            columns: [],
            data: []
          }} onBackToQuery={() => setSelectedTable(null)} />
        ) : (
          <>
            <QueryEditor
              query={currentQuery}
              onQueryChange={handleQueryChange}
              onExecute={handleExecuteQuery}
              isLoading={isLoading}
            />
            <ResultsSection results={results} isLoading={isLoading} error={error} />
          </>
        )}
      </main>
    </div>
  )
}
