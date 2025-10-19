"use client"

import { useState, useEffect } from "react"

interface ResultsSectionProps {
  results: Record<string, any>[]
  isLoading?: boolean
  error?: string | null
  metadata?: any
}

export function ResultsSection({ results, isLoading = false, error = null, metadata = null }: ResultsSectionProps) {
  const [activeTab, setActiveTab] = useState<"results" | "answer">("results")

  // Si es que hay metadata nueva, cambiar la pestaña activa según el tipo de consulta y resultados
  useEffect(() => {
    if (metadata) {
      if (results && results.length > 0) {
        setActiveTab("results")
      }
      else if (metadata.queryType !== "select") {
        setActiveTab("answer")
      }
    }
  }, [results, metadata])

  const columns = results && results.length > 0 ? Object.keys(results[0]) : []

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mb-6">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab("results")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === "results" ? "text-white" : "text-gray-400 hover:text-white"
            }`}
            style={{
              backgroundColor: activeTab === "results" ? "#1193d4" : "transparent",
            }}
          >
            Resultados de Tabla{" "}
            {results.length > 0 && (
              <span className="ml-1 px-2 py-0.5 bg-black/20 rounded text-xs">{results.length}</span>
            )}
          </button>
          <button
            onClick={() => setActiveTab("answer")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === "answer" ? "text-white" : "text-gray-400 hover:text-white"
            }`}
            style={{
              backgroundColor: activeTab === "answer" ? "#1193d4" : "transparent",
            }}
          >
            Respuesta
          </button>
        </div>
      </div>

      {/* Content based on active tab */}
      {activeTab === "results" ? (
        <>
          {isLoading ? (
            <div className="flex items-center justify-center h-32" style={{ color: "#6b7280" }}>
              <div className="flex items-center space-x-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[#1193d4]"></div>
                <span>Ejecutando consulta...</span>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-32" style={{ color: "#ef4444" }}>
              <div className="text-center">
                <div className="font-medium">Error de Consulta</div>
                <div className="text-sm mt-1">{error}</div>
              </div>
            </div>
          ) : !results || results.length === 0 ? (
            <div className="flex items-center justify-center h-32" style={{ color: "#6b7280" }}>
              No hay resultados para mostrar
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border" style={{ borderColor: "#2a3b43" }}>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y" style={{ backgroundColor: "#1a2b33" }}>
                  <thead style={{ backgroundColor: "#2a3b43" }}>
                    <tr>
                      {columns.map((column) => (
                        <th
                          key={column}
                          scope="col"
                          className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider"
                          style={{ color: "#9ca3af" }}
                        >
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y" style={{ backgroundColor: "#1a2b33", borderColor: "#2a3b43" }}>
                    {results.map((row, index) => (
                      <tr key={index}>
                        {columns.map((column, colIndex) => (
                          <td
                            key={column}
                            className={`whitespace-nowrap px-6 py-4 text-sm ${colIndex === 0 ? "font-medium" : ""}`}
                            style={{
                              color: colIndex === 0 ? "#e5e7eb" : "#9ca3af",
                            }}
                          >
                            {row[column]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="p-6">
          {isLoading ? (
            <div className="flex items-center justify-center h-32" style={{ color: "#6b7280" }}>
              <div className="flex items-center space-x-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[#1193d4]"></div>
                <span>Ejecutando consulta...</span>
              </div>
            </div>
          ) : error ? (

            <div className="flex items-center justify-center h-32" style={{ color: "#ef4444" }}>
              <div className="text-center">
                <div className="font-medium">Error de Consulta</div>
                <div className="text-sm mt-1">{error}</div>
              </div>
            </div>
          ) : metadata ? (
            <div className="space-y-4">
              <div className="rounded-lg border p-4" style={{ borderColor: "#2a3b43", backgroundColor: "#1a2b33" }}>
                <h3 className="text-lg font-semibold mb-3" style={{ color: "#e5e7eb" }}>Resumen de Consulta</h3>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span style={{ color: "#9ca3af" }}>Tipo de operación:</span>
                    <span className="font-medium" style={{ color: "#e5e7eb" }}>{metadata.queryType?.toUpperCase()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span style={{ color: "#9ca3af" }}>Mensaje:</span>
                    <span className="font-medium" style={{ color: "#e5e7eb" }}>{metadata.message}</span>
                  </div>
                  {metadata.affectedRows !== null && metadata.affectedRows !== undefined && (
                    <div className="flex justify-between">
                      <span style={{ color: "#9ca3af" }}>Filas afectadas:</span>
                      <span className="font-medium" style={{ color: "#1193d4" }}>{metadata.affectedRows}</span>
                    </div>
                  )}
                  {metadata.executionTime && (
                    <div className="flex justify-between">
                      <span style={{ color: "#9ca3af" }}>Tiempo de ejecución:</span>
                      <span className="font-medium" style={{ color: "#1193d4" }}>{metadata.executionTime} ms</span>
                    </div>
                  )}
                  {metadata.metadata?.table_name && (
                    <div className="flex justify-between">
                      <span style={{ color: "#9ca3af" }}>Tabla:</span>
                      <span className="font-medium" style={{ color: "#e5e7eb" }}>{metadata.metadata.table_name}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-32" style={{ color: "#6b7280" }}>
              <span>Ejecuta una consulta para ver los resultados</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
