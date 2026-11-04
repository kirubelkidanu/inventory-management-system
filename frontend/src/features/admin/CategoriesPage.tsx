import React, { useState, useMemo } from 'react'
import {
  FolderTree,
  Plus,
  Search,
  Edit2,
  Power,
  Archive,
  RefreshCw,
  Package,
  CheckCircle2,
  AlertTriangle,
  Loader2,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useCategories, useToggleCategoryStatus } from '@/features/inventory/useInventoryData'
import type { Category } from '@/types'
import { CategoryModal } from './components/CategoryModal'

export const CategoriesPage: React.FC = () => {
  const { hasRole } = useAuth()
  const isAdmin = hasRole('ADMIN')

  const [searchQuery, setSearchQuery] = useState('')
  const [includeArchived, setIncludeArchived] = useState(true)

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null)

  // Status Toggle Mutation
  const toggleStatusMutation = useToggleCategoryStatus()
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const {
    data: categories = [],
    isLoading,
    isRefetching,
    refetch,
    error,
  } = useCategories({
    includeArchived,
    search: searchQuery,
  })

  // Filtered categories
  const filteredCategories = useMemo(() => {
    return categories.filter((cat) => {
      if (!includeArchived && !cat.is_active) {
        return false
      }
      if (!searchQuery.trim()) return true
      const q = searchQuery.toLowerCase().trim()
      return (
        cat.code.toLowerCase().includes(q) ||
        cat.name.toLowerCase().includes(q) ||
        (cat.description && cat.description.toLowerCase().includes(q))
      )
    })
  }, [categories, includeArchived, searchQuery])

  // Summary counts
  const totalCount = categories.length
  const activeCount = useMemo(() => categories.filter((c) => c.is_active).length, [categories])
  const archivedCount = totalCount - activeCount

  const handleOpenCreate = () => {
    setSelectedCategory(null)
    setIsModalOpen(true)
  }

  const handleOpenEdit = (category: Category) => {
    setSelectedCategory(category)
    setIsModalOpen(true)
  }

  const handleToggleStatus = async (category: Category) => {
    if (!isAdmin) return
    setActionError(null)
    setTogglingId(category.id)
    try {
      await toggleStatusMutation.mutateAsync({
        id: category.id,
        is_active: !category.is_active,
      })
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to update category status.'
      setActionError(msg)
    } finally {
      setTogglingId(null)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 bg-blue-50 text-blue-700 rounded-xl border border-blue-200/60 shadow-xs">
              <FolderTree className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900">Category Master</h1>
              <p className="text-xs text-slate-500">
                Manage material classifications, inventory categories, and SKU prefixes
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isLoading || isRefetching}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 shadow-xs transition-colors disabled:opacity-50"
            title="Refresh categories"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefetching ? 'animate-spin text-blue-600' : ''}`} />
            <span>Refresh</span>
          </button>

          {isAdmin && (
            <button
              type="button"
              onClick={handleOpenCreate}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Add Category</span>
            </button>
          )}
        </div>
      </div>

      {/* KPI Stats Ribbon */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500">Total Categories</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{totalCount}</p>
          </div>
          <div className="p-2.5 bg-slate-50 text-slate-600 rounded-lg border border-slate-100">
            <FolderTree className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500">Active Classifications</p>
            <p className="text-2xl font-bold text-emerald-700 mt-1">{activeCount}</p>
          </div>
          <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-lg border border-emerald-100">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500">Archived Categories</p>
            <p className="text-2xl font-bold text-slate-600 mt-1">{archivedCount}</p>
          </div>
          <div className="p-2.5 bg-slate-50 text-slate-500 rounded-lg border border-slate-100">
            <Archive className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Action Error Banner */}
      {actionError && (
        <div className="flex items-start gap-2.5 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search category code (e.g. 01, 15) or name (e.g. CEMENT, CLEAN)..."
            className="w-full pl-9 pr-4 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-slate-50/50"
          />
        </div>

        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-slate-700 font-medium">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(e) => setIncludeArchived(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
            <span>Include archived categories</span>
          </label>
        </div>
      </div>

      {/* Table Section */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center">
            <Loader2 className="w-7 h-7 animate-spin mx-auto text-blue-600 mb-2" />
            <p className="text-xs text-slate-500">Loading category master data...</p>
          </div>
        ) : error ? (
          <div className="p-10 text-center text-red-600 text-xs">
            Failed to load categories. Please check your network connection or server status.
          </div>
        ) : filteredCategories.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <FolderTree className="w-10 h-10 mx-auto text-slate-300 mb-2" />
            <p className="text-sm font-semibold text-slate-800">No categories found</p>
            <p className="text-xs text-slate-400 mt-1">
              {searchQuery ? 'Try adjusting your search filter.' : 'Click "+ Add Category" to create one.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4 w-28">Category Code</th>
                  <th className="py-3 px-4 w-56">Category Name</th>
                  <th className="py-3 px-4">Description</th>
                  <th className="py-3 px-4 w-36 text-center">Active Items</th>
                  <th className="py-3 px-4 w-28 text-center">Status</th>
                  {isAdmin && <th className="py-3 px-4 w-32 text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredCategories.map((cat) => {
                  const isCurrentToggling = togglingId === cat.id
                  return (
                    <tr
                      key={cat.id}
                      className={`hover:bg-slate-50/70 transition-colors ${
                        !cat.is_active ? 'bg-slate-50/40 text-slate-400' : ''
                      }`}
                    >
                      {/* Code Badge */}
                      <td className="py-3 px-4 font-mono font-bold text-slate-900">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono font-bold bg-slate-100 text-slate-800 border border-slate-200 shadow-2xs">
                          {cat.code}
                        </span>
                      </td>

                      {/* Name */}
                      <td className="py-3 px-4 font-semibold text-slate-800">
                        {cat.name}
                      </td>

                      {/* Description */}
                      <td className="py-3 px-4 text-slate-500 truncate max-w-sm">
                        {cat.description || <span className="text-slate-300 italic">None</span>}
                      </td>

                      {/* Active Items Count */}
                      <td className="py-3 px-4 text-center">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                          <Package className="w-3 h-3 text-slate-400" />
                          <span>{cat.item_count ?? 0}</span>
                        </span>
                      </td>

                      {/* Status */}
                      <td className="py-3 px-4 text-center">
                        {cat.is_active ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-500 border border-slate-200">
                            Archived
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      {isAdmin && (
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleOpenEdit(cat)}
                              className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                              title="Edit Category"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>

                            <button
                              type="button"
                              onClick={() => handleToggleStatus(cat)}
                              disabled={isCurrentToggling}
                              className={`p-1.5 rounded-md transition-colors ${
                                cat.is_active
                                  ? 'text-slate-500 hover:text-amber-700 hover:bg-amber-50'
                                  : 'text-slate-500 hover:text-emerald-700 hover:bg-emerald-50'
                              }`}
                              title={cat.is_active ? 'Archive Category' : 'Reactivate Category'}
                            >
                              {isCurrentToggling ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Power className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="px-4 py-3 bg-slate-50/60 border-t border-slate-200 text-xs text-slate-500 flex items-center justify-between">
          <span>
            Showing <strong className="text-slate-800">{filteredCategories.length}</strong> of{' '}
            <strong className="text-slate-800">{categories.length}</strong> categories
          </span>
          {!isAdmin && (
            <span className="text-[11px] text-slate-400 italic">
              View-only mode: Category management requires Administrator privileges.
            </span>
          )}
        </div>
      </div>

      {/* Modal Dialog */}
      <CategoryModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        category={selectedCategory}
      />
    </div>
  )
}

export default CategoriesPage
