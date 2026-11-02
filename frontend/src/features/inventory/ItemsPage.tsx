import React, { useState, useMemo } from 'react'
import {
  Search,
  Filter,
  RotateCw,
  Eye,
  Pencil,
  Plus,
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  XCircle,
  Package,
  Upload,
  Trash2,
  RotateCcw,
  AlertTriangle,
  AlertCircle,
  X,
  Loader2,
} from 'lucide-react'
import type { Item } from '@/types'
import {
  useItems,
  useCategories,
  useCreateItem,
  useUpdateItem,
  useDeleteItem,
  useBulkDeleteItems,
  useRestoreItem,
} from './useInventoryData'
import { useAuth } from '@/context/AuthContext'
import { ItemDetailsDrawer } from './ItemDetailsDrawer'
import { ImportItemsModal } from './components/ImportItemsModal'
import { cn } from '@/lib/utils'

const UNIT_CHIPS = ['PCS', 'KG', 'BAG', 'M2', 'M3', 'ROLL', 'SET', 'LTR']

const getErrorMessage = (err: unknown, defaultMsg: string): string => {
  if (err && typeof err === 'object' && 'response' in err) {
    const res = (err as { response?: { data?: { detail?: unknown } } }).response
    if (res?.data?.detail) {
      if (typeof res.data.detail === 'string') return res.data.detail
      if (Array.isArray(res.data.detail)) {
        return res.data.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(', ')
      }
    }
  }
  if (err instanceof Error) return err.message
  return defaultMsg
}

export const ItemsPage: React.FC = () => {
  const { hasRole } = useAuth()
  const isAdmin = hasRole('ADMIN')
  const isManager = hasRole('ADMIN', 'INVENTORY_MANAGER')

  // Search & filter state
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [includeArchived, setIncludeArchived] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  // Selection state
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(new Set())

  // Modal & Drawer state
  const [selectedItem, setSelectedItem] = useState<Item | null>(null)
  const [isImportModalOpen, setIsImportModalOpen] = useState(false)
  const [confirmModalState, setConfirmModalState] = useState<{
    isOpen: boolean
    mode: 'single' | 'bulk'
    item?: Item
  }>({ isOpen: false, mode: 'bulk' })

  // Add Item Modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [addForm, setAddForm] = useState({
    item_code: '',
    description: '',
    category_id: '',
    default_unit: 'PCS',
    is_active: true,
  })
  const [addError, setAddError] = useState<string | null>(null)

  // Edit Item Modal state
  const [editItem, setEditItem] = useState<Item | null>(null)
  const [editForm, setEditForm] = useState({
    description: '',
    category_id: '',
    default_unit: 'PCS',
    is_active: true,
  })
  const [editError, setEditError] = useState<string | null>(null)

  // Notification alert banner
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'info'
    message: string
  } | null>(null)

  // Mutations
  const createItemMutation = useCreateItem()
  const updateItemMutation = useUpdateItem()
  const deleteItemMutation = useDeleteItem()
  const bulkDeleteMutation = useBulkDeleteItems()
  const restoreItemMutation = useRestoreItem()

  // Queries
  const { data: categories } = useCategories()

  const categoryMap = useMemo(() => {
    return new Map((categories || []).map((c) => [c.id, c.name]))
  }, [categories])

  const skip = (page - 1) * pageSize
  const {
    data: itemsData,
    isLoading,
    isFetching,
    refetch,
  } = useItems({
    search: debouncedSearch,
    category_id: selectedCategory || undefined,
    include_inactive: includeArchived,
    skip,
    limit: pageSize,
  })

  const items = itemsData?.items || []
  const totalItems = itemsData?.total || 0
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))

  // Selection handlers
  const isAllPageSelected =
    items.length > 0 && items.every((i) => selectedItemIds.has(i.id))

  const toggleSelectAllPage = () => {
    setSelectedItemIds((prev) => {
      const next = new Set(prev)
      if (isAllPageSelected) {
        items.forEach((i) => next.delete(i.id))
      } else {
        items.forEach((i) => next.add(i.id))
      }
      return next
    })
  }

  const toggleSelectItem = (id: string) => {
    setSelectedItemIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const clearSelection = () => {
    setSelectedItemIds(new Set())
  }

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setDebouncedSearch(searchInput)
    setPage(1)
  }

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedCategory(e.target.value)
    setPage(1)
  }

  const handleToggleIncludeArchived = (e: React.ChangeEvent<HTMLInputElement>) => {
    setIncludeArchived(e.target.checked)
    setPage(1)
  }

  // Create submission
  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setAddError(null)
    try {
      const created = await createItemMutation.mutateAsync({
        item_code: addForm.item_code.trim(),
        description: addForm.description.trim(),
        category_id: addForm.category_id,
        default_unit: addForm.default_unit.trim(),
        is_active: addForm.is_active,
      })
      setIsAddModalOpen(false)
      setAddForm({
        item_code: '',
        description: '',
        category_id: categories?.[0]?.id || '',
        default_unit: 'PCS',
        is_active: true,
      })
      setNotification({
        type: 'success',
        message: `Item "${created.item_code}" was created successfully.`,
      })
    } catch (err: unknown) {
      setAddError(getErrorMessage(err, 'Failed to create item.'))
    }
  }

  // Edit submission
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editItem) return
    setEditError(null)
    try {
      const updated = await updateItemMutation.mutateAsync({
        id: editItem.id,
        payload: {
          description: editForm.description.trim(),
          category_id: editForm.category_id,
          default_unit: editForm.default_unit.trim(),
          is_active: editForm.is_active,
        },
      })
      setEditItem(null)
      setNotification({
        type: 'success',
        message: `Item "${updated.item_code}" was updated successfully.`,
      })
    } catch (err: unknown) {
      setEditError(getErrorMessage(err, 'Failed to update item.'))
    }
  }

  // Deletion execution
  const executeDelete = async () => {
    try {
      if (confirmModalState.mode === 'single' && confirmModalState.item) {
        const itemToDelete = confirmModalState.item
        const res = await deleteItemMutation.mutateAsync(itemToDelete.id)
        setNotification({
          type: 'success',
          message:
            res.outcome === 'ARCHIVED'
              ? `Item "${itemToDelete.item_code}" has existing inventory/transactions and was safely archived.`
              : `Item "${itemToDelete.item_code}" was permanently deleted.`,
        })
        setSelectedItemIds((prev) => {
          const next = new Set(prev)
          next.delete(itemToDelete.id)
          return next
        })
      } else if (confirmModalState.mode === 'bulk') {
        const ids = Array.from(selectedItemIds)
        if (ids.length === 0) return
        const res = await bulkDeleteMutation.mutateAsync(ids)
        setNotification({
          type: 'success',
          message: `Bulk operation complete: ${res.deleted_count} items permanently deleted, ${res.archived_count} items safely archived.`,
        })
        clearSelection()
      }
    } catch (err: unknown) {
      const errMsg =
        err instanceof Error ? err.message : 'An error occurred while processing the request.'
      setNotification({
        type: 'error',
        message: `Deletion failed: ${errMsg}`,
      })
    } finally {
      setConfirmModalState({ isOpen: false, mode: 'bulk' })
    }
  }

  // Restore execution
  const handleRestoreItem = async (item: Item) => {
    try {
      await restoreItemMutation.mutateAsync(item.id)
      setNotification({
        type: 'success',
        message: `Item "${item.item_code}" has been restored to the active catalog.`,
      })
    } catch (err: unknown) {
      const errMsg =
        err instanceof Error ? err.message : 'Failed to restore item.'
      setNotification({
        type: 'error',
        message: `Restore failed: ${errMsg}`,
      })
    }
  }

  const isDeleting =
    deleteItemMutation.isPending || bulkDeleteMutation.isPending

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Item Master Catalog
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Authoritative SKU definitions, category classifications, and global warehouse stock audit ledgers.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isManager && (
            <button
              type="button"
              onClick={() => {
                setAddForm((prev) => ({
                  ...prev,
                  category_id: prev.category_id || categories?.[0]?.id || '',
                }))
                setIsAddModalOpen(true)
                setAddError(null)
              }}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-emerald-500 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add New Item</span>
            </button>
          )}
          {isAdmin && (
            <button
              type="button"
              onClick={() => setIsImportModalOpen(true)}
              className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-sky-500 transition-colors"
            >
              <Upload className="h-3.5 w-3.5" />
              <span>Import from Excel</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition-colors"
          >
            <RotateCw className={cn('h-3.5 w-3.5', (isLoading || isFetching) && 'animate-spin')} />
            <span>Refresh Catalog</span>
          </button>
        </div>
      </div>

      {/* Notification Banner */}
      {notification && (
        <div
          className={cn(
            'flex items-center justify-between rounded-xl p-4 text-sm font-medium border shadow-xs',
            notification.type === 'success' && 'bg-emerald-50 text-emerald-800 border-emerald-200',
            notification.type === 'error' && 'bg-rose-50 text-rose-800 border-rose-200',
            notification.type === 'info' && 'bg-sky-50 text-sky-800 border-sky-200'
          )}
        >
          <div className="flex items-center gap-2.5">
            {notification.type === 'success' && <CheckCircle className="h-5 w-5 text-emerald-600 shrink-0" />}
            {notification.type === 'error' && <AlertCircle className="h-5 w-5 text-rose-600 shrink-0" />}
            {notification.type === 'info' && <AlertCircle className="h-5 w-5 text-sky-600 shrink-0" />}
            <span>{notification.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setNotification(null)}
            className="rounded-lg p-1 hover:bg-black/5 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Search & Category Filter Bar */}
      <div className="flex flex-col md:flex-row md:items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
        <form onSubmit={handleSearchSubmit} className="relative flex-1">
          <Search className="pointer-events-none absolute inset-y-0 left-0 my-auto ml-3 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search by SKU code or description (Press Enter)..."
            className="block w-full rounded-lg border border-slate-300 py-2 pl-9 pr-20 text-sm placeholder-slate-400 focus:border-sky-500 focus:outline-hidden"
          />
          <button
            type="submit"
            className="absolute inset-y-1.5 right-1.5 rounded-md bg-slate-100 px-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-200"
          >
            Search
          </button>
        </form>

        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[200px]">
            <select
              value={selectedCategory}
              onChange={handleCategoryChange}
              className="block w-full rounded-lg border border-slate-300 py-2 pl-3 pr-8 text-sm focus:border-sky-500 focus:outline-hidden bg-white"
            >
              <option value="">All Item Categories</option>
              {(categories || []).map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name} ({cat.code})
                </option>
              ))}
            </select>
          </div>

          {/* Include Archived Items Toggle */}
          <label className="inline-flex items-center gap-2 cursor-pointer select-none text-xs font-medium text-slate-700 bg-slate-50 border border-slate-200 px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={handleToggleIncludeArchived}
              className="h-4 w-4 rounded-sm border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            <span>Include archived items</span>
          </label>

          {debouncedSearch && (
            <button
              type="button"
              onClick={() => {
                setSearchInput('')
                setDebouncedSearch('')
                setPage(1)
              }}
              className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-500 hover:bg-slate-50"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Bulk Selection Action Bar */}
      {isAdmin && selectedItemIds.size > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50/80 px-4 py-3 shadow-xs animate-in fade-in duration-200">
          <div className="flex items-center gap-2 text-sm font-semibold text-rose-900">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-rose-200 text-xs font-bold text-rose-800">
              {selectedItemIds.size}
            </span>
            <span>item{selectedItemIds.size > 1 ? 's' : ''} selected</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={clearSelection}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Clear Selection
            </button>
            <button
              type="button"
              onClick={() => setConfirmModalState({ isOpen: true, mode: 'bulk' })}
              className="inline-flex items-center gap-1.5 rounded-lg bg-rose-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-rose-500"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Delete / Archive Selected</span>
            </button>
          </div>
        </div>
      )}

      {/* Catalog Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold text-slate-500 uppercase">
              <tr>
                {isAdmin && (
                  <th scope="col" className="w-10 px-4 py-3.5 text-center">
                    <input
                      type="checkbox"
                      checked={isAllPageSelected}
                      onChange={toggleSelectAllPage}
                      title="Select all on this page"
                      className="h-4 w-4 rounded-sm border-slate-300 text-sky-600 focus:ring-sky-500"
                    />
                  </th>
                )}
                <th scope="col" className="px-6 py-3.5">SKU Code</th>
                <th scope="col" className="px-6 py-3.5">Description</th>
                <th scope="col" className="px-6 py-3.5">Category</th>
                <th scope="col" className="px-6 py-3.5">Default Unit</th>
                <th scope="col" className="px-6 py-3.5">Status</th>
                <th scope="col" className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {isLoading ? (
                <tr>
                  <td colSpan={isAdmin ? 7 : 6} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <div className="h-6 w-6 animate-spin rounded-full border-2 border-sky-500 border-t-transparent" />
                      <span className="text-xs">Loading item catalog...</span>
                    </div>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={isAdmin ? 7 : 6} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Package className="h-8 w-8 text-slate-300" />
                      <span className="text-sm font-medium text-slate-700">No items found</span>
                      <p className="text-xs text-slate-400">
                        Try adjusting your search filters or category selection.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const catName =
                    item.category?.name ||
                    categoryMap.get(item.category_id) ||
                    'General Catalog'
                  const isSelected = selectedItemIds.has(item.id)

                  return (
                    <tr
                      key={item.id}
                      className={cn(
                        'hover:bg-slate-50/70 transition-colors',
                        isSelected && 'bg-rose-50/30'
                      )}
                    >
                      {isAdmin && (
                        <td className="w-10 px-4 py-4 text-center">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelectItem(item.id)}
                            className="h-4 w-4 rounded-sm border-slate-300 text-sky-600 focus:ring-sky-500"
                          />
                        </td>
                      )}
                      <td className="px-6 py-4">
                        <span className="inline-flex rounded-md border border-slate-200 bg-slate-100 px-2 py-0.5 font-mono text-xs font-bold text-slate-900">
                          {item.item_code}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="font-medium text-slate-800" title={item.description}>
                          {item.description}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
                          <Filter className="h-3 w-3 text-slate-400" />
                          {catName}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono text-xs text-slate-600">
                        {item.default_unit}
                      </td>
                      <td className="px-6 py-4">
                        {item.is_active ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-200">
                            <CheckCircle className="h-3 w-3" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 border border-slate-200">
                            <XCircle className="h-3 w-3" />
                            Archived
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => setSelectedItem(item)}
                            title="View Stock & Ledger"
                            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-sky-600 shadow-xs hover:bg-sky-50 hover:border-sky-300 transition-colors"
                          >
                            <Eye className="h-3.5 w-3.5" />
                            <span className="hidden sm:inline">View</span>
                          </button>

                          {isManager && (
                            <button
                              type="button"
                              onClick={() => {
                                setEditItem(item)
                                setEditForm({
                                  description: item.description,
                                  category_id: item.category_id,
                                  default_unit: item.default_unit,
                                  is_active: item.is_active,
                                })
                                setEditError(null)
                              }}
                              title="Edit Item Details"
                              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-amber-700 shadow-xs hover:bg-amber-50 hover:border-amber-300 transition-colors"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                              <span className="hidden sm:inline">Edit</span>
                            </button>
                          )}

                          {isAdmin && !item.is_active && (
                            <button
                              type="button"
                              onClick={() => handleRestoreItem(item)}
                              disabled={restoreItemMutation.isPending}
                              title="Restore item to active catalog"
                              className="inline-flex items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-700 shadow-xs hover:bg-emerald-100 transition-colors disabled:opacity-50"
                            >
                              <RotateCcw className="h-3.5 w-3.5" />
                              <span className="hidden sm:inline">Restore</span>
                            </button>
                          )}

                          {isAdmin && (
                            <button
                              type="button"
                              onClick={() =>
                                setConfirmModalState({
                                  isOpen: true,
                                  mode: 'single',
                                  item,
                                })
                              }
                              title="Delete or archive item"
                              className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white p-1.5 text-xs font-semibold text-slate-500 shadow-xs hover:bg-rose-50 hover:border-rose-300 hover:text-rose-600 transition-colors"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-slate-200 bg-white px-6 py-3.5">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span>Rows per page:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value))
                setPage(1)
              }}
              className="rounded-md border border-slate-300 py-1 px-2 text-xs focus:outline-hidden"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
            <span className="ml-2">
              Showing <span className="font-semibold">{totalItems === 0 ? 0 : skip + 1}</span> to{' '}
              <span className="font-semibold">{Math.min(skip + pageSize, totalItems)}</span> of{' '}
              <span className="font-semibold">{totalItems}</span> items
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Previous</span>
            </button>
            <span className="px-2 text-xs font-medium text-slate-600">
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 disabled:opacity-40"
            >
              <span>Next</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Confirmation Modal */}
      {confirmModalState.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-rose-100 text-rose-600">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-900">
                  {confirmModalState.mode === 'single'
                    ? `Delete or Archive Item: ${confirmModalState.item?.item_code}`
                    : `Delete or Archive ${selectedItemIds.size} Selected Items`}
                </h3>
                <p className="mt-1 text-sm text-slate-600">
                  Unused items will be permanently deleted. Items with transaction or stock history will be safely archived to preserve the audit ledger.
                </p>
              </div>
            </div>

            <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800">
              <strong>Referential Integrity Protection:</strong> Active stock and ledger transactions will never be orphaned. Inactive items can be restored at any time.
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setConfirmModalState({ isOpen: false, mode: 'bulk' })}
                disabled={isDeleting}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={executeDelete}
                disabled={isDeleting}
                className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-rose-500 disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>Confirm Delete / Archive</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add New Item Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
                  <Plus className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">Add New Inventory Item</h3>
                  <p className="text-xs text-slate-500">Register a new catalog SKU definition</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setIsAddModalOpen(false)
                  setAddError(null)
                }}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {addError && (
              <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                <span>{addError}</span>
              </div>
            )}

            <form onSubmit={handleAddSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Item Code / SKU <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={addForm.item_code}
                  onChange={(e) => setAddForm((prev) => ({ ...prev, item_code: e.target.value.toUpperCase() }))}
                  placeholder="e.g. 01-CM-00001 or ST-BAR-12"
                  className="block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm font-mono placeholder-slate-400 focus:border-emerald-500 focus:outline-hidden"
                />
                <p className="mt-1 text-[11px] text-slate-400">Unique identifier across the inventory master catalog.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Description <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={addForm.description}
                  onChange={(e) => setAddForm((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="e.g. Portland Pozzolana Cement (PPC) 50KG Bag"
                  className="block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm placeholder-slate-400 focus:border-emerald-500 focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Category <span className="text-rose-500">*</span>
                </label>
                <select
                  required
                  value={addForm.category_id}
                  onChange={(e) => setAddForm((prev) => ({ ...prev, category_id: e.target.value }))}
                  className="block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-emerald-500 focus:outline-hidden bg-white"
                >
                  <option value="" disabled>Select Item Category</option>
                  {(categories || []).map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name} ({cat.code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Default Unit of Measure (UOM) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={addForm.default_unit}
                  onChange={(e) => setAddForm((prev) => ({ ...prev, default_unit: e.target.value.toUpperCase() }))}
                  placeholder="e.g. PCS, KG, BAG"
                  className="block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm font-mono focus:border-emerald-500 focus:outline-hidden"
                />
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className="text-[11px] text-slate-400 mr-1">Quick Select:</span>
                  {UNIT_CHIPS.map((chip) => (
                    <button
                      key={chip}
                      type="button"
                      onClick={() => setAddForm((prev) => ({ ...prev, default_unit: chip }))}
                      className={cn(
                        'rounded-md px-2 py-0.5 text-xs font-mono font-medium transition-colors border',
                        addForm.default_unit === chip
                          ? 'bg-emerald-100 text-emerald-800 border-emerald-300 font-bold'
                          : 'bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200'
                      )}
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              </div>

              <div className="pt-1">
                <label className="inline-flex items-center gap-2 cursor-pointer select-none text-xs font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={addForm.is_active}
                    onChange={(e) => setAddForm((prev) => ({ ...prev, is_active: e.target.checked }))}
                    className="h-4 w-4 rounded-sm border-slate-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>Active in Catalog (Available for stock receiving & issuing)</span>
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => {
                    setIsAddModalOpen(false)
                    setAddError(null)
                  }}
                  disabled={createItemMutation.isPending}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createItemMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-emerald-500 disabled:opacity-50"
                >
                  {createItemMutation.isPending ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <>
                      <Plus className="h-3.5 w-3.5" />
                      <span>Create Item</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Item Modal */}
      {editItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
                  <Pencil className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">Edit Item Master</h3>
                  <p className="text-xs text-slate-500">Update specification, category, and UOM</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setEditItem(null)
                  setEditError(null)
                }}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {editError && (
              <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                <span>{editError}</span>
              </div>
            )}

            <form onSubmit={handleEditSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Item Code / SKU (Immutable)
                </label>
                <input
                  type="text"
                  disabled
                  value={editItem.item_code}
                  className="block w-full rounded-lg border border-slate-200 bg-slate-100 py-2 px-3 text-sm font-mono text-slate-500 cursor-not-allowed"
                />
                <p className="mt-1 text-[11px] text-slate-400">SKU codes are immutable to protect transaction ledger integrity.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Description <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={editForm.description}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="Detailed item description"
                  className="block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-amber-500 focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Category <span className="text-rose-500">*</span>
                </label>
                <select
                  required
                  value={editForm.category_id}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, category_id: e.target.value }))}
                  className="block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-amber-500 focus:outline-hidden bg-white"
                >
                  {(categories || []).map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name} ({cat.code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Default Unit of Measure (UOM) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={editForm.default_unit}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, default_unit: e.target.value.toUpperCase() }))}
                  placeholder="e.g. PCS, KG, BAG"
                  className="block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm font-mono focus:border-amber-500 focus:outline-hidden"
                />
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className="text-[11px] text-slate-400 mr-1">Quick Select:</span>
                  {UNIT_CHIPS.map((chip) => (
                    <button
                      key={chip}
                      type="button"
                      onClick={() => setEditForm((prev) => ({ ...prev, default_unit: chip }))}
                      className={cn(
                        'rounded-md px-2 py-0.5 text-xs font-mono font-medium transition-colors border',
                        editForm.default_unit === chip
                          ? 'bg-amber-100 text-amber-800 border-amber-300 font-bold'
                          : 'bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200'
                      )}
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              </div>

              <div className="pt-1">
                <label className="inline-flex items-center gap-2 cursor-pointer select-none text-xs font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={editForm.is_active}
                    onChange={(e) => setEditForm((prev) => ({ ...prev, is_active: e.target.checked }))}
                    className="h-4 w-4 rounded-sm border-slate-300 text-amber-600 focus:ring-amber-500"
                  />
                  <span>Active in Catalog</span>
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => {
                    setEditItem(null)
                    setEditError(null)
                  }}
                  disabled={updateItemMutation.isPending}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateItemMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-amber-500 disabled:opacity-50"
                >
                  {updateItemMutation.isPending ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Pencil className="h-3.5 w-3.5" />
                      <span>Save Changes</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Slide-over Item Details Drawer */}
      {selectedItem && (
        <ItemDetailsDrawer
          item={selectedItem}
          categoryName={
            selectedItem.category?.name ||
            categoryMap.get(selectedItem.category_id)
          }
          onClose={() => setSelectedItem(null)}
        />
      )}

      {/* Item Master Excel Import Modal */}
      <ImportItemsModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onSuccess={() => {
          refetch()
        }}
      />
    </div>
  )
}

export default ItemsPage
