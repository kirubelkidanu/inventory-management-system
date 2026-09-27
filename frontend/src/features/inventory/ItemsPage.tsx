import React, { useState, useMemo } from 'react'
import {
  Search,
  Filter,
  RotateCw,
  Eye,
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  XCircle,
  Package,
  Upload,
} from 'lucide-react'
import type { Item } from '@/types'
import { useItems, useCategories } from './useInventoryData'
import { ItemDetailsDrawer } from './ItemDetailsDrawer'
import { ImportItemsModal } from './components/ImportItemsModal'
import { cn } from '@/lib/utils'

export const ItemsPage: React.FC = () => {
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [selectedItem, setSelectedItem] = useState<Item | null>(null)
  const [isImportModalOpen, setIsImportModalOpen] = useState(false)

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
    skip,
    limit: pageSize,
  })

  const items = itemsData?.items || []
  const totalItems = itemsData?.total || 0
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setDebouncedSearch(searchInput)
    setPage(1)
  }

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedCategory(e.target.value)
    setPage(1)
  }

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
          <button
            type="button"
            onClick={() => setIsImportModalOpen(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-sky-500"
          >
            <Upload className="h-3.5 w-3.5" />
            <span>Import from Excel</span>
          </button>
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50"
          >
            <RotateCw className={cn('h-3.5 w-3.5', (isLoading || isFetching) && 'animate-spin')} />
            <span>Refresh Catalog</span>
          </button>
        </div>
      </div>

      {/* Search & Category Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
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

        <div className="flex items-center gap-2">
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

      {/* Catalog Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold text-slate-500 uppercase">
              <tr>
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
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <div className="h-6 w-6 animate-spin rounded-full border-2 border-sky-500 border-t-transparent" />
                      <span className="text-xs">Loading item catalog...</span>
                    </div>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
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

                  return (
                    <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
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
                        <button
                          type="button"
                          onClick={() => setSelectedItem(item)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-sky-600 shadow-xs hover:bg-sky-50 hover:border-sky-300 transition-colors"
                        >
                          <Eye className="h-3.5 w-3.5" />
                          <span>View Stock & Ledger</span>
                        </button>
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
