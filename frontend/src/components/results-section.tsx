"use client"

import { useState } from "react"

interface ResultsSectionProps {
  results: Record<string, any>[]
  isLoading?: boolean
  error?: string | null
}

export function ResultsSection({ results, isLoading = false, error = null }: ResultsSectionProps) {
  const [activeTab, setActiveTab] = useState<"results" | "answer">("results")

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
        <div className="flex items-center justify-center h-32" style={{ color: "#6b7280" }}>
          {isLoading ? (
            <div className="flex items-center space-x-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[#1193d4]"></div>
              <span>Executing query...</span>
            </div>
          ) : error ? (
            <div className="text-center" style={{ color: "#ef4444" }}>
              <div className="font-medium">Query Error</div>
              <div className="text-sm mt-1">{error}</div>
            </div>
          ) : (
            <span>Consulta ejecutada exitosamente. {results.length} filas devueltas.</span>
          )}
        </div>
      )}
    </div>
  )
}
