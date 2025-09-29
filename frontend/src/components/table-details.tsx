"use client"

import { ArrowLeft, Check, X } from "lucide-react"

interface TableColumn {
  name: string
  type: string
  indexed: boolean
  indexType: string | null
  primaryKey: boolean
}

interface TableSchema {
  name: string
  description: string
  columns: TableColumn[]
  data: Record<string, any>[]
}

interface TableDetailsProps {
  table: TableSchema
  onBackToQuery: () => void
}

export function TableDetails({ table, onBackToQuery }: TableDetailsProps) {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mb-6">
        <button
          onClick={onBackToQuery}
          className="inline-flex items-center text-sm hover:text-[#e5e7eb] mb-4"
          style={{ color: "#9ca3af" }}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Volver a Consulta
        </button>
        <nav className="flex items-center text-sm mb-4">
          <span className="font-medium" style={{ color: "#9ca3af" }}>
            Datos
          </span>
          <span className="mx-2" style={{ color: "#6b7280" }}>
            /
          </span>
          <span className="font-medium" style={{ color: "#9ca3af" }}>
            Bases de Datos
          </span>
          <span className="mx-2" style={{ color: "#6b7280" }}>
            /
          </span>
          <span className="font-medium" style={{ color: "#e5e7eb" }}>
            {table.name}
          </span>
        </nav>
        <h2 className="text-3xl font-bold tracking-tight" style={{ color: "#e5e7eb" }}>
          {table.name}
        </h2>
        <p className="mt-1" style={{ color: "#9ca3af" }}>
          {table.description}
        </p>
      </div>

      <div className="space-y-12">
        {/* Schema Section */}
        <div>
          <h3 className="text-xl font-semibold mb-4" style={{ color: "#e5e7eb" }}>
            Esquema
          </h3>
          <div className="overflow-hidden rounded-lg border" style={{ borderColor: "#2a3b43" }}>
            <table className="min-w-full divide-y" style={{ backgroundColor: "#1a2b33" }}>
              <thead style={{ backgroundColor: "#2a3b43" }}>
                <tr>
                  <th className="w-1/3 px-4 py-3.5 text-left text-sm font-semibold" style={{ color: "#e5e7eb" }}>
                    Columna
                  </th>
                  <th className="px-4 py-3.5 text-left text-sm font-semibold" style={{ color: "#e5e7eb" }}>
                    Tipo
                  </th>
                  <th className="px-4 py-3.5 text-center text-sm font-semibold" style={{ color: "#e5e7eb" }}>
                    Indexado
                  </th>
                  <th className="px-4 py-3.5 text-center text-sm font-semibold" style={{ color: "#e5e7eb" }}>
                    Clave Primaria
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ backgroundColor: "#1a2b33", borderColor: "#2a3b43" }}>
                {table.columns.map((column) => (
                  <tr key={column.name}>
                    <td className="whitespace-nowrap px-4 py-4 text-sm font-medium" style={{ color: "#e5e7eb" }}>
                      {column.name}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-sm" style={{ color: "#9ca3af" }}>
                      {column.type}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-center">
                      {column.indexed ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-[#1193d4]/20 text-[#1193d4]">
                          {column.indexType}
                        </span>
                      ) : (
                        <X className="h-4 w-4 mx-auto" style={{ color: "#6b7280" }} />
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-center">
                      {column.primaryKey ? (
                        <Check className="h-4 w-4 text-[#1193d4] mx-auto" />
                      ) : (
                        <X className="h-4 w-4 mx-auto" style={{ color: "#6b7280" }} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Data Preview Section */}
        <div>
          <h3 className="text-xl font-semibold mb-4" style={{ color: "#e5e7eb" }}>
            Vista Previa de Datos
          </h3>
          <div className="overflow-x-auto">
            <div
              className="inline-block min-w-full overflow-hidden rounded-lg border"
              style={{ borderColor: "#2a3b43" }}
            >
              <table className="min-w-full divide-y" style={{ backgroundColor: "#1a2b33" }}>
                <thead style={{ backgroundColor: "#2a3b43" }}>
                  <tr>
                    {table.columns.map((column) => (
                      <th
                        key={column.name}
                        className="px-4 py-3.5 text-left text-sm font-semibold"
                        style={{ color: "#e5e7eb" }}
                      >
                        {column.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ backgroundColor: "#1a2b33", borderColor: "#2a3b43" }}>
                  {table.data.map((row, index) => (
                    <tr key={index}>
                      {table.columns.map((column) => (
                        <td
                          key={column.name}
                          className="whitespace-nowrap px-4 py-4 text-sm"
                          style={{ color: "#9ca3af" }}
                        >
                          {row[column.name]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
