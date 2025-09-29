"use client"

import { Play, Loader2 } from "lucide-react"

interface QueryEditorProps {
  query: string
  onQueryChange: (query: string) => void
  onExecute: () => void
  isLoading?: boolean
}

export function QueryEditor({ query, onQueryChange, onExecute, isLoading = false }: QueryEditorProps) {
  return (
    <div className="p-6 border-b" style={{ borderColor: "#2a3b43" }}>
      <div className="space-y-4">
        <div>
          <label htmlFor="sql-query" className="block text-sm font-medium mb-2" style={{ color: "#e5e7eb" }}>
            Consulta SQL
          </label>
          <textarea
            id="sql-query"
            name="sql-query"
            rows={8}
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="SELECT * FROM usuarios;"
            className="block w-full rounded-lg p-3 shadow-sm focus:border-[#1193d4] focus:ring-[#1193d4] sm:text-sm font-mono"
            style={{
              backgroundColor: "#1a2b33",
              borderColor: "#2a3b43",
              color: "#e5e7eb",
              border: "1px solid #2a3b43",
            }}
          />
        </div>
        <div className="flex justify-end">
          <button
            onClick={onExecute}
            disabled={isLoading}
            className="inline-flex items-center justify-center rounded-lg bg-[#1193d4] px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[#1193d4]/90 focus:outline-none focus:ring-2 focus:ring-[#1193d4] focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundColor: "#1193d4" }}
          >
            {isLoading ? (
              <Loader2 className="mr-2 -ml-1 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 -ml-1 h-4 w-4" />
            )}
            {isLoading ? "Ejecutando..." : "Ejecutar"}
          </button>
        </div>
      </div>
    </div>
  )
}
