"use client"

import { useState } from "react"
import { Play, Copy, Menu, ChevronLeft, History, Database, ChevronDown, ChevronUp } from "lucide-react"

interface QueryHistoryItem {
  query: string
  timestamp: string
  isActive: boolean
}

interface SidebarProps {
  tables: string[]
  queryHistory: QueryHistoryItem[]
  activeTab: "queries" | "tables"
  onTabChange: (tab: "queries" | "tables") => void
  onHistoryItemClick: (query: string) => void
  onTableClick: (tableName: string) => void
  selectedTable: string | null
  collapsed: boolean
  onToggleCollapse: () => void
}

export function Sidebar({
  tables,
  queryHistory,
  activeTab,
  onTabChange,
  onHistoryItemClick,
  onTableClick,
  selectedTable,
  collapsed,
  onToggleCollapse,
}: SidebarProps) {
  const [showAllQueries, setShowAllQueries] = useState(false)
  const [showAllTables, setShowAllTables] = useState(false)

  const displayedQueries = showAllQueries ? queryHistory : queryHistory.slice(0, 10)
  const displayedTables = showAllTables ? tables : tables.slice(0, 10)


  return (
    <aside
      className={`border-r flex flex-col transition-all duration-300 ${collapsed ? "w-16" : "w-80"}`}
      style={{ backgroundColor: "#1a2833", borderColor: "#2a3843" }}
    >
      {/* Header */}
      <div className="flex h-16 shrink-0 items-center gap-4 border-b px-6" style={{ borderColor: "#2a3843" }}>
        <button
          onClick={onToggleCollapse}
          className="flex items-center justify-center w-6 h-6 rounded hover:bg-[#2a3843]"
          style={{ color: "#1193d4" }}
        >
          {collapsed ? <Menu className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>

        {!collapsed && (
          <>
            <div className="size-6 text-[#1193d4]">
              <svg fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M36.7273 44C33.9891 44 31.6043 39.8386 30.3636 33.69C29.123 39.8386 26.7382 44 24 44C21.2618 44 18.877 39.8386 17.6364 33.69C16.3957 39.8386 14.0109 44 11.2727 44C7.25611 44 4 35.0457 4 24C4 12.9543 7.25611 4 11.2727 4C14.0109 4 16.3957 8.16144 17.6364 14.31C18.877 8.16144 21.2618 4 24 4C26.7382 4 29.123 8.16144 30.3636 14.31C31.6043 8.16144 33.9891 4 36.7273 4C40.7439 4 44 12.9543 44 24C44 35.0457 40.7439 44 36.7273 44Z"
                  fill="currentColor"
                />
              </svg>
            </div>
            <h1 className="text-xl font-bold" style={{ color: "#e5e7eb" }}>
              ConsultaBD
            </h1>
          </>
        )}
      </div>

      {collapsed ? (
        <div className="flex flex-col items-center gap-4 p-4">
          <button
            onClick={() => onTabChange("queries")}
            className={`flex items-center justify-center w-8 h-8 rounded transition-colors ${
              activeTab === "queries" ? "bg-[#1193d4]/20" : "hover:bg-[#2a3843]"
            }`}
            style={{ color: activeTab === "queries" ? "#1193d4" : "#9ca3af" }}
            title="Historial de Consultas"
          >
            <History className="w-4 h-4" />
          </button>
          <button
            onClick={() => onTabChange("tables")}
            className={`flex items-center justify-center w-8 h-8 rounded transition-colors ${
              activeTab === "tables" ? "bg-[#1193d4]/20" : "hover:bg-[#2a3843]"
            }`}
            style={{ color: activeTab === "tables" ? "#1193d4" : "#9ca3af" }}
            title="Tablas de la Base de Datos"
          >
            <Database className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <>
          {/* Tab Navigation */}
          <div className="border-b relative" style={{ borderColor: "#2a3843" }}>
            <div className="flex relative">
              {/* Animated background slider */}
              <div
                className="absolute bottom-0 h-0.5 bg-[#1193d4] transition-transform duration-300 ease-in-out"
                style={{
                  width: "50%",
                  transform: activeTab === "queries" ? "translateX(0%)" : "translateX(100%)"
                }}
              />
              <button
                onClick={() => onTabChange("queries")}
                className={`flex-1 px-4 py-3 text-center text-sm font-medium relative transition-all duration-300 ${
                  activeTab === "queries" ? "text-[#1193d4]" : "hover:text-[#e5e7eb]"
                }`}
                style={{ color: activeTab === "queries" ? "#1193d4" : "#9ca3af" }}
              >
                Consultas
              </button>
              <button
                onClick={() => onTabChange("tables")}
                className={`flex-1 px-4 py-3 text-center text-sm font-medium relative transition-all duration-300 ${
                  activeTab === "tables" ? "text-[#1193d4]" : "hover:text-[#e5e7eb]"
                }`}
                style={{ color: activeTab === "tables" ? "#1193d4" : "#9ca3af" }}
              >
                Tablas
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4 relative">
            <div
              className={`transition-all duration-300 ease-in-out ${
                activeTab === "queries"
                  ? "opacity-100 transform translate-x-0"
                  : "opacity-0 transform -translate-x-4 absolute inset-0 pointer-events-none"
              }`}
            >
              {activeTab === "queries" && (
              <>
                <h2 className="mb-4 text-lg font-bold" style={{ color: "#e5e7eb" }}>
                  Historial
                </h2>
                <nav className="space-y-1">
                  {displayedQueries.map((item, index) => (
                    <div
                      key={index}
                      className="group rounded px-3 py-2 hover:bg-[#1193d4]/20 cursor-pointer"
                      onClick={() => onHistoryItemClick(item.query)}
                    >
                      <p
                        className={`truncate text-sm font-medium ${item.isActive ? "text-[#1193d4]" : ""}`}
                        style={{ color: item.isActive ? "#1193d4" : "#9ca3af" }}
                      >
                        {item.query}
                      </p>
                      <div className="mt-1 flex items-center justify-between text-xs" style={{ color: "#6b7280" }}>
                        <span>{item.timestamp}</span>
                        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100">
                          <button className="rounded p-1 hover:bg-[#2a3843]">
                            <Play className="h-3 w-3" />
                          </button>
                          <button className="rounded p-1 hover:bg-[#2a3843]">
                            <Copy className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </nav>
                {queryHistory.length > 10 && (
                  <button
                    onClick={() => setShowAllQueries(!showAllQueries)}
                    className="mt-4 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:bg-[#1193d4]/20"
                    style={{ color: "#1193d4" }}
                  >
                    {showAllQueries ? (
                      <>
                        <ChevronUp className="h-4 w-4" />
                        Mostrar menos
                      </>
                    ) : (
                      <>
                        <ChevronDown className="h-4 w-4" />
                        Mostrar {queryHistory.length - 10} más
                      </>
                    )}
                  </button>
                )}
              </>
              )}
            </div>
            <div
              className={`transition-all duration-300 ease-in-out ${
                activeTab === "tables"
                  ? "opacity-100 transform translate-x-0"
                  : "opacity-0 transform translate-x-4 absolute inset-0 pointer-events-none"
              }`}
            >
              {activeTab === "tables" && (
              <>
                <h2 className="mb-4 text-lg font-bold" style={{ color: "#e5e7eb" }}>
                  Tablas
                </h2>
                <nav className="space-y-1">
                  {displayedTables.map((table) => (
                    <button
                      key={table}
                      onClick={() => onTableClick(table)}
                      className={`block w-full text-left rounded px-3 py-2 text-sm ${
                        selectedTable === table ? "bg-[#1193d4]/20 font-medium text-[#1193d4]" : "hover:bg-[#1193d4]/20"
                      }`}
                      style={{
                        color: selectedTable === table ? "#1193d4" : "#9ca3af",
                        backgroundColor: selectedTable === table ? "rgba(17, 147, 212, 0.2)" : "transparent",
                      }}
                    >
                      {table}
                    </button>
                  ))}
                </nav>
                {tables.length > 10 && (
                  <button
                    onClick={() => setShowAllTables(!showAllTables)}
                    className="mt-4 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:bg-[#1193d4]/20"
                    style={{ color: "#1193d4" }}
                  >
                    {showAllTables ? (
                      <>
                        <ChevronUp className="h-4 w-4" />
                        Mostrar menos
                      </>
                    ) : (
                      <>
                        <ChevronDown className="h-4 w-4" />
                        Mostrar {tables.length - 10} más
                      </>
                    )}
                  </button>
                )}
              </>
              )}
            </div>
          </div>
        </>
      )}
    </aside>
  )
}
