import React, { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Search,
  RotateCw,
  Warehouse as WarehouseIcon,
  PackageCheck,
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  Truck,
  ShieldCheck,
  PackageX,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { useInventoryBalances, useWarehouses, useCategories } from './useInventoryData'
import { cn } from '@/lib/utils'

export const InventoryBalancesPage: React.FC = () => {
  const [selectedWarehouse, setSelectedWarehouse] = useState<string>('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [searchInput, setSearchInput] = useState<string>('')
  const [debouncedSearch, setDebouncedSearch] = useState<string>('')
  const [includeArchived, setIncludeArchived] = useState<boolean>(false)
  const [hideZeroStock, setHideZeroStock] = useState<boolean>(false)
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(50)

  const { data: warehouses } = useWarehouses()
  const { data: categories } = useCategories()

  const {
    data: balances,
    isLoading,
    isFetching,
    refetch,
  } = useInventoryBalances({
    warehouse_id: selectedWarehouse || undefined,
    category_id: selectedCategory || undefined,
    search: debouncedSearch || undefined,
    include_inactive_warehouses: includeArchived,
  })

  const rawList = balances || []
  const filteredList = useMemo(() => {
    if (!hideZeroStock) return rawList
    return rawList.filter((b) => Number(b.quantity_on_hand || 0) > 0)
  }, [rawList, hideZeroStock])

  // Compute stat strip metrics from full filtered dataset (not just current page)
  const totalLines = filteredList.length
  const totalOnHand = useMemo(
    () => filteredList.reduce((sum, b) => sum + Number(b.quantity_on_hand || 0), 0),
    [filteredList]
  )
  const totalReserved = useMemo(
    () => filteredList.reduce((sum, b) => sum + Number(b.quantity_reserved || 0), 0),
    [filteredList]
  )
  const depletedCount = useMemo(
    () => filteredList.filter((b) => Number(b.quantity_on_hand || 0) <= 0).length,
    [filteredList]
  )

  const totalPages = Math.max(1, Math.ceil(totalLines / pageSize))
  const safePage = Math.min(page, totalPages)
  const paginatedList = useMemo(() => {
    const start = (safePage - 1) * pageSize
    return filteredList.slice(start, start + pageSize)
  }, [filteredList, safePage, pageSize])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setDebouncedSearch(searchInput)
    setPage(1)
  }

  const getStockStatusBadge = (onHand: number, reserved: number, available: number) => {
    if (onHand <= 0) {
      return (
        <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700 border border-red-200">
          <PackageX className="h-3 w-3 shrink-0" />
          Out of Stock
        </span>
      )
    }
    if (reserved > 0) {
      return (
        <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700 border border-amber-200">
          <AlertTriangle className="h-3 w-3 shrink-0" />
          Reserved Active
        </span>
      )
    }
    if (available > 0) {
      return (
        <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200">
          <PackageCheck className="h-3 w-3 shrink-0" />
          In Stock
        </span>
      )
    }
    return (
      <span className="inline-flex items-center whitespace-nowrap rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
        Neutral
      </span>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Real-Time Warehouse Stock Balances
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Authoritative projected quantities on hand, reserved commitments, and available inventory.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-500 bg-white border border-slate-200 px-3 py-1.5 rounded-lg">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            <span>Dual-Write Balance Protection Active</span>
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50"
          >
            <RotateCw className={cn('h-3.5 w-3.5', (isLoading || isFetching) && 'animate-spin')} />
            <span>Sync Live Balances</span>
          </button>
        </div>
      </div>

      {/* Summary Stat Strip */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="block truncate text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Total Line Projections
          </span>
          <p
            title={totalLines.toLocaleString()}
            className="mt-2 truncate text-2xl font-extrabold text-slate-900 font-mono tabular-nums"
          >
            {totalLines.toLocaleString()}
          </p>
          <p className="mt-1 truncate text-xs text-slate-400">Warehouse SKU allocations</p>
        </div>

        <div className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="block truncate text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Total Physical Quantity
          </span>
          <p
            title={totalOnHand.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            className="mt-2 truncate text-2xl font-extrabold text-slate-900 font-mono tabular-nums"
          >
            {totalOnHand.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="mt-1 truncate text-xs text-slate-400">Gross On-Hand inventory</p>
        </div>

        <div className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="block truncate text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Reserved Allocations
          </span>
          <p
            title={totalReserved.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            className="mt-2 truncate text-2xl font-extrabold text-amber-600 font-mono tabular-nums"
          >
            {totalReserved.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="mt-1 truncate text-xs text-slate-400">Committed to active orders</p>
        </div>

        <div className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="block truncate text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Depleted / Zero Stock
          </span>
          <p
            title={depletedCount.toLocaleString()}
            className="mt-2 truncate text-2xl font-extrabold text-red-600 font-mono tabular-nums"
          >
            {depletedCount.toLocaleString()}
          </p>
          <p className="mt-1 truncate text-xs text-slate-400">SKUs requiring replenishment</p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
        {/* Warehouse Dropdown */}
        <div>
          <label className="block text-xs font-semibold text-slate-600">Store / Warehouse</label>
          <div className="relative mt-1">
            <select
              value={selectedWarehouse}
              onChange={(e) => {
                setSelectedWarehouse(e.target.value)
                setPage(1)
              }}
              className="block w-full rounded-lg border border-slate-300 py-2 pl-3 pr-8 text-sm focus:border-sky-500 focus:outline-hidden bg-white"
            >
              <option value="">All Operating Stores</option>
              {(warehouses || [])
                .filter((wh) => includeArchived || wh.is_active)
                .map((wh) => (
                  <option key={wh.id} value={wh.id}>
                    {wh.name} ({wh.code}){!wh.is_active ? ' [Archived]' : ''}
                  </option>
                ))}
            </select>
          </div>
        </div>

        {/* Category Dropdown */}
        <div>
          <label className="block text-xs font-semibold text-slate-600">Classification</label>
          <div className="relative mt-1">
            <select
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value)
                setPage(1)
              }}
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
        </div>

        {/* Search & Filter Toggles */}
        <div>
          <label className="block text-xs font-semibold text-slate-600">SKU Code / Description</label>
          <form onSubmit={handleSearchSubmit} className="relative mt-1">
            <Search className="pointer-events-none absolute inset-y-0 left-0 my-auto ml-3 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search SKU or item name..."
              className="block w-full rounded-lg border border-slate-300 py-2 pl-9 pr-16 text-sm placeholder-slate-400 focus:border-sky-500 focus:outline-hidden"
            />
            <button
              type="submit"
              className="absolute inset-y-1.5 right-1.5 rounded-md bg-slate-100 px-2 text-xs font-semibold text-slate-700 hover:bg-slate-200"
            >
              Filter
            </button>
          </form>
          <div className="mt-2 flex flex-wrap items-center justify-end gap-4">
            <label className="inline-flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer select-none hover:text-slate-800">
              <input
                type="checkbox"
                checked={hideZeroStock}
                onChange={(e) => {
                  setHideZeroStock(e.target.checked)
                  setPage(1)
                }}
                className="rounded border-slate-300 text-sky-600 focus:ring-sky-500 h-3.5 w-3.5"
              />
              <span>Hide zero stock</span>
            </label>
            <label className="inline-flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer select-none hover:text-slate-800">
              <input
                type="checkbox"
                checked={includeArchived}
                onChange={(e) => {
                  setIncludeArchived(e.target.checked)
                  setPage(1)
                }}
                className="rounded border-slate-300 text-sky-600 focus:ring-sky-500 h-3.5 w-3.5"
              />
              <span>Include archived stores</span>
            </label>
          </div>
        </div>
      </div>

      {/* Balances Data Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                <th scope="col" className="px-4 py-3 whitespace-nowrap min-w-[180px]">Store Location</th>
                <th scope="col" className="px-4 py-3 whitespace-nowrap">SKU Code</th>
                <th scope="col" className="px-4 py-3">Description</th>
                <th scope="col" className="px-4 py-3 whitespace-nowrap">Category</th>
                <th scope="col" className="px-4 py-3 whitespace-nowrap">Unit</th>
                <th scope="col" className="px-4 py-3 text-right whitespace-nowrap">On Hand</th>
                <th scope="col" className="px-4 py-3 text-right whitespace-nowrap">Reserved</th>
                <th scope="col" className="px-4 py-3 text-right whitespace-nowrap">Available Stock</th>
                <th scope="col" className="px-4 py-3 text-center whitespace-nowrap">Status</th>
                <th scope="col" className="px-4 py-3 text-right whitespace-nowrap">Fast Vouchers</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {isLoading ? (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <div className="h-6 w-6 animate-spin rounded-full border-2 border-sky-500 border-t-transparent" />
                      <span className="text-xs">Calculating live stock projections...</span>
                    </div>
                  </td>
                </tr>
              ) : totalLines === 0 ? (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <WarehouseIcon className="h-8 w-8 text-slate-300" />
                      <span className="text-sm font-medium text-slate-700">
                        No inventory balances matched
                      </span>
                      <p className="text-xs text-slate-400">
                        Try selecting another store or clearing filter criteria.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedList.map((row) => {
                  const onHand = Number(row.quantity_on_hand) || 0
                  const reserved = Number(row.quantity_reserved) || 0
                  const available = Number(row.available_quantity) || onHand - reserved

                  return (
                    <tr key={`${row.warehouse_id}-${row.item_id}`} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-4 py-2.5 min-w-[180px]">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900 whitespace-nowrap">{row.warehouse_name}</span>
                          {row.warehouse_is_active === false && (
                            <span className="inline-flex items-center rounded-sm bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800 whitespace-nowrap">
                              Archived
                            </span>
                          )}
                        </div>
                        <span className="font-mono text-[11px] text-slate-400">
                          {row.warehouse_code}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap">
                        <span className="inline-flex whitespace-nowrap rounded-md border border-slate-200 bg-slate-100 px-2 py-0.5 font-mono text-xs font-bold text-slate-900">
                          {row.item_code}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-700 font-medium min-w-[200px]">
                        {row.item_description}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-slate-500 whitespace-nowrap">{row.category_name}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-slate-600 whitespace-nowrap">{row.unit}</td>
                      <td className="px-4 py-2.5 text-right font-mono font-bold tabular-nums text-slate-900 whitespace-nowrap">
                        {onHand.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono tabular-nums text-amber-600 whitespace-nowrap">
                        {reserved.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono font-extrabold tabular-nums text-emerald-600 whitespace-nowrap">
                        {available.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                      </td>
                      <td className="px-4 py-2.5 text-center whitespace-nowrap">
                        {getStockStatusBadge(onHand, reserved, available)}
                      </td>
                      <td className="px-4 py-2.5 text-right whitespace-nowrap">
                        <div className="inline-flex items-center gap-1">
                          <Link
                            to={`/transactions/grv?item_id=${row.item_id}&warehouse_id=${row.warehouse_id}`}
                            title="Receive goods into this store"
                            className="rounded-md border border-emerald-200 bg-emerald-50 p-1.5 text-emerald-700 hover:bg-emerald-100"
                          >
                            <ArrowDownToLine className="h-3.5 w-3.5" />
                          </Link>
                          <Link
                            to={`/transactions/siv?item_id=${row.item_id}&warehouse_id=${row.warehouse_id}`}
                            title="Issue goods from this store"
                            className="rounded-md border border-sky-200 bg-sky-50 p-1.5 text-sky-700 hover:bg-sky-100"
                          >
                            <ArrowUpFromLine className="h-3.5 w-3.5" />
                          </Link>
                          <Link
                            to={`/transactions/istv?item_id=${row.item_id}&warehouse_id=${row.warehouse_id}`}
                            title="Transfer stock to another store"
                            className="rounded-md border border-purple-200 bg-purple-50 p-1.5 text-purple-700 hover:bg-purple-100"
                          >
                            <Truck className="h-3.5 w-3.5" />
                          </Link>
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
        {totalLines > 0 && (
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-t border-slate-200 px-4 py-3 gap-3 bg-slate-50/50 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-slate-500">Rows per page:</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value))
                  setPage(1)
                }}
                className="rounded-lg border border-slate-300 py-1 px-2 text-xs bg-white focus:outline-hidden"
              >
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
              <span className="text-slate-500 ml-2">
                Showing {Math.min((safePage - 1) * pageSize + 1, totalLines)}–
                {Math.min(safePage * pageSize, totalLines)} of {totalLines.toLocaleString()} balances
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-500">
                Page {safePage} of {totalPages}
              </span>
              <button
                type="button"
                aria-label="Previous"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage <= 1}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                <span>Previous</span>
              </button>
              <button
                type="button"
                aria-label="Next"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage >= totalPages}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-30 transition-colors"
              >
                <span>Next</span>
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default InventoryBalancesPage
