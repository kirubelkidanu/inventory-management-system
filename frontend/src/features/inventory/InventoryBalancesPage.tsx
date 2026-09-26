import React, { useState } from 'react'
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
} from 'lucide-react'
import { useInventoryBalances, useWarehouses, useCategories } from './useInventoryData'
import { cn } from '@/lib/utils'

export const InventoryBalancesPage: React.FC = () => {
  const [selectedWarehouse, setSelectedWarehouse] = useState<string>('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [searchInput, setSearchInput] = useState<string>('')
  const [debouncedSearch, setDebouncedSearch] = useState<string>('')

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
  })

  const rawList = balances || []

  // Compute stat strip metrics
  const totalLines = rawList.length
  const totalOnHand = rawList.reduce((sum, b) => sum + Number(b.quantity_on_hand || 0), 0)
  const totalReserved = rawList.reduce((sum, b) => sum + Number(b.quantity_reserved || 0), 0)
  const depletedCount = rawList.filter((b) => Number(b.quantity_on_hand || 0) <= 0).length

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setDebouncedSearch(searchInput)
  }

  const getStockStatusBadge = (onHand: number, reserved: number, available: number) => {
    if (onHand <= 0) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700 border border-red-200">
          <PackageX className="h-3 w-3" />
          Out of Stock
        </span>
      )
    }
    if (reserved > 0) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700 border border-amber-200">
          <AlertTriangle className="h-3 w-3" />
          Reserved Active
        </span>
      )
    }
    if (available > 0) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200">
          <PackageCheck className="h-3 w-3" />
          In Stock
        </span>
      )
    }
    return (
      <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
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
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Total Line Projections
          </span>
          <p className="mt-2 text-2xl font-extrabold text-slate-900 font-mono">
            {totalLines.toLocaleString()}
          </p>
          <p className="mt-1 text-xs text-slate-400">Warehouse SKU allocations</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Total Physical Quantity
          </span>
          <p className="mt-2 text-2xl font-extrabold text-slate-900 font-mono">
            {totalOnHand.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="mt-1 text-xs text-slate-400">Gross On-Hand inventory</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Reserved Allocations
          </span>
          <p className="mt-2 text-2xl font-extrabold text-amber-600 font-mono">
            {totalReserved.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="mt-1 text-xs text-slate-400">Committed to active orders</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Depleted / Zero Stock
          </span>
          <p className="mt-2 text-2xl font-extrabold text-red-600 font-mono">
            {depletedCount}
          </p>
          <p className="mt-1 text-xs text-slate-400">SKUs requiring replenishment</p>
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
              onChange={(e) => setSelectedWarehouse(e.target.value)}
              className="block w-full rounded-lg border border-slate-300 py-2 pl-3 pr-8 text-sm focus:border-sky-500 focus:outline-hidden bg-white"
            >
              <option value="">All Operating Stores</option>
              {(warehouses || []).map((wh) => (
                <option key={wh.id} value={wh.id}>
                  {wh.name} ({wh.code})
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
              onChange={(e) => setSelectedCategory(e.target.value)}
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

        {/* Search */}
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
        </div>
      </div>

      {/* Balances Data Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold text-slate-500 uppercase">
              <tr>
                <th scope="col" className="px-5 py-3.5">Store Location</th>
                <th scope="col" className="px-5 py-3.5">SKU Code</th>
                <th scope="col" className="px-5 py-3.5">Description</th>
                <th scope="col" className="px-5 py-3.5">Category</th>
                <th scope="col" className="px-5 py-3.5">Unit</th>
                <th scope="col" className="px-5 py-3.5 text-right">On Hand</th>
                <th scope="col" className="px-5 py-3.5 text-right">Reserved</th>
                <th scope="col" className="px-5 py-3.5 text-right">Available Stock</th>
                <th scope="col" className="px-5 py-3.5 text-center">Status</th>
                <th scope="col" className="px-5 py-3.5 text-right">Fast Vouchers</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {isLoading ? (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <div className="h-6 w-6 animate-spin rounded-full border-2 border-sky-500 border-t-transparent" />
                      <span className="text-xs">Calculating live stock projections...</span>
                    </div>
                  </td>
                </tr>
              ) : rawList.length === 0 ? (
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
                rawList.map((row) => {
                  const onHand = Number(row.quantity_on_hand) || 0
                  const reserved = Number(row.quantity_reserved) || 0
                  const available = Number(row.available_quantity) || onHand - reserved

                  return (
                    <tr key={`${row.warehouse_id}-${row.item_id}`} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-5 py-4">
                        <div className="font-semibold text-slate-900">{row.warehouse_name}</div>
                        <span className="font-mono text-[11px] text-slate-400">
                          {row.warehouse_code}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <span className="inline-flex rounded-md border border-slate-200 bg-slate-100 px-2 py-0.5 font-mono text-xs font-bold text-slate-900">
                          {row.item_code}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-slate-700 font-medium">
                        {row.item_description}
                      </td>
                      <td className="px-5 py-4 text-xs text-slate-500">{row.category_name}</td>
                      <td className="px-5 py-4 font-mono text-xs text-slate-600">{row.unit}</td>
                      <td className="px-5 py-4 text-right font-mono font-bold text-slate-900">
                        {onHand.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                      </td>
                      <td className="px-5 py-4 text-right font-mono text-amber-600">
                        {reserved.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                      </td>
                      <td className="px-5 py-4 text-right font-mono font-extrabold text-emerald-600">
                        {available.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                      </td>
                      <td className="px-5 py-4 text-center">
                        {getStockStatusBadge(onHand, reserved, available)}
                      </td>
                      <td className="px-5 py-4 text-right">
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
      </div>
    </div>
  )
}

export default InventoryBalancesPage
