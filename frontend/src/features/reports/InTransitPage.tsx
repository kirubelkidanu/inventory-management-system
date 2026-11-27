import React, { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Truck,
  PackageOpen,
  RefreshCw,
  Search,
  CheckCircle2,
  ArrowRight,
  Loader2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { useWarehouses } from '@/features/inventory/useInventoryData'
import { useInTransitReport, type InTransitFilterParams } from './useReportData'

export const InTransitPage: React.FC = () => {
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [sourceWarehouseId, setSourceWarehouseId] = useState('')
  const [destWarehouseId, setDestWarehouseId] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  const { data: warehouses = [] } = useWarehouses()

  const queryParams: InTransitFilterParams = {
    source_warehouse_id: sourceWarehouseId || undefined,
    destination_warehouse_id: destWarehouseId || undefined,
    status: statusFilter !== 'ALL' ? statusFilter : undefined,
    search: search || undefined,
  }

  const { data: rawTransfers = [], isLoading, isFetching, refetch } = useInTransitReport(queryParams)

  // Client search filter across ISTV #, ref #, invoice #, plate, driver, or item code
  const transfers = useMemo(() => {
    if (!search.trim()) return rawTransfers
    const q = search.toLowerCase().trim()
    return rawTransfers.filter(
      (t) =>
        t.istv_number?.toLowerCase().includes(q) ||
        t.istv_no?.toLowerCase().includes(q) ||
        t.invoice_no?.toLowerCase().includes(q) ||
        t.plate_no?.toLowerCase().includes(q) ||
        t.driver_name?.toLowerCase().includes(q) ||
        t.item_code?.toLowerCase().includes(q) ||
        t.item_description?.toLowerCase().includes(q)
    )
  }, [rawTransfers, search])

  const totalLines = transfers.length
  const totalPages = Math.max(1, Math.ceil(totalLines / pageSize))
  const safePage = Math.min(page, totalPages)
  const paginatedTransfers = useMemo(() => {
    const start = (safePage - 1) * pageSize
    return transfers.slice(start, start + pageSize)
  }, [transfers, safePage, pageSize])

  const getStatusBadge = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'IN_TRANSIT':
        return 'bg-purple-50 text-purple-700 border-purple-200'
      case 'PARTIALLY_RECEIVED':
        return 'bg-amber-50 text-amber-700 border-amber-200'
      case 'COMPLETED':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200'
      default:
        return 'bg-slate-50 text-slate-600 border-slate-200'
    }
  }

  const activeInTransitCount = rawTransfers.filter(
    (t) => t.status !== 'COMPLETED' && Number(t.remaining_quantity) > 0
  ).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-purple-100 p-2.5 text-purple-700 shadow-xs">
            <Truck className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                Logistics & In-Transit Tracking
              </h1>
              <span className="rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-bold text-purple-800">
                {activeInTransitCount} Active En-Route
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              Real-time audit tracking of dispatched store transfers, transport vehicles, drivers, and pending receipt balances.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/transactions/istv"
            className="inline-flex items-center gap-1.5 rounded-xl bg-purple-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-purple-500 transition-colors"
          >
            <Truck className="h-3.5 w-3.5" />
            <span>+ New Transfer (ISTV)</span>
          </Link>
          <Link
            to="/transactions/istrv"
            className="inline-flex items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-teal-500 transition-colors"
          >
            <PackageOpen className="h-3.5 w-3.5" />
            <span>Receive Goods (ISTRV)</span>
          </Link>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs space-y-3">
        {/* Status Pills */}
        <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-100 pb-3">
          {[
            { id: 'ALL', label: 'All Shipments' },
            { id: 'IN_TRANSIT', label: 'Active In-Transit' },
            { id: 'PARTIALLY_RECEIVED', label: 'Partially Received' },
            { id: 'COMPLETED', label: 'Completed' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setStatusFilter(tab.id)
                setPage(1)
              }}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                statusFilter === tab.id
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Secondary filters */}
        <div className="flex flex-wrap items-center gap-3 pt-1">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search ISTV #, ref #, invoice/waybill, plate, driver, or SKU..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-xs focus:border-slate-500 focus:outline-hidden"
            />
          </div>

          <div className="w-52">
            <select
              value={sourceWarehouseId}
              onChange={(e) => {
                setSourceWarehouseId(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs focus:border-slate-500 focus:outline-hidden"
            >
              <option value="">Origin (FROM): All</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
          </div>

          <div className="w-52">
            <select
              value={destWarehouseId}
              onChange={(e) => {
                setDestWarehouseId(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs focus:border-slate-500 focus:outline-hidden"
            >
              <option value="">Destination (TO): All</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* In-Transit Logistics Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50/80 font-semibold text-slate-600 uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-2.5 px-4 whitespace-nowrap">Dispatch Date</th>
                <th className="py-2.5 px-4 whitespace-nowrap">ISTV Number</th>
                <th className="py-2.5 px-4 whitespace-nowrap">Origin & Destination Route</th>
                <th className="py-2.5 px-4 whitespace-nowrap">Vehicle & Driver</th>
                <th className="py-2.5 px-4">Item SKU & Description</th>
                <th className="py-2.5 px-4 text-right whitespace-nowrap">Dispatched</th>
                <th className="py-2.5 px-4 text-right whitespace-nowrap">Received</th>
                <th className="py-2.5 px-4 text-right whitespace-nowrap">Remaining In-Transit</th>
                <th className="py-2.5 px-4 text-center whitespace-nowrap">Status</th>
                <th className="py-2.5 px-4 text-right whitespace-nowrap">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {isLoading ? (
                <tr>
                  <td colSpan={10} className="py-16 text-center text-slate-400">
                    <Loader2 className="mx-auto h-7 w-7 animate-spin text-slate-400 mb-2" />
                    <span>Loading in-transit logistics movements...</span>
                  </td>
                </tr>
              ) : totalLines === 0 ? (
                <tr>
                  <td colSpan={10} className="py-16 text-center text-slate-400">
                    <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500 mb-2" />
                    <p className="font-semibold text-slate-700">No active shipments in transit</p>
                    <p className="text-xs text-slate-400 mt-0.5">All dispatched inventory transfers have been safely received.</p>
                  </td>
                </tr>
              ) : (
                paginatedTransfers.map((item) => {
                  const sentQty = Number(item.sent_quantity ?? item.dispatched_quantity ?? 0)
                  const recvQty = Number(item.received_quantity ?? 0)
                  const remQty = Number(item.remaining_quantity ?? 0)
                  const isPending = remQty > 0

                  return (
                    <tr key={`${item.transfer_record_id}-${item.item_id}`} className="hover:bg-slate-50/75 transition-colors">
                      <td className="py-2.5 px-4 whitespace-nowrap font-mono text-slate-600">
                        {item.transfer_date || item.transaction_date || '—'}
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap font-mono">
                        <div className="font-bold text-purple-900 whitespace-nowrap">{item.istv_number}</div>
                        {(item.istv_no || item.invoice_no) && (
                          <div className="text-[10px] text-slate-500 font-normal space-y-0.5 mt-0.5 whitespace-nowrap">
                            {item.istv_no && <div>Ref: {item.istv_no}</div>}
                            {item.invoice_no && <div>Inv/WB: {item.invoice_no}</div>}
                          </div>
                        )}
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        <div className="font-semibold text-slate-800">{item.source_warehouse_name}</div>
                        <div className="text-slate-400 flex items-center gap-1 text-[11px]">
                          <span>&rarr;</span>
                          <span>{item.destination_warehouse_name}</span>
                        </div>
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        <div className="font-mono text-slate-800 flex items-center gap-1 font-medium whitespace-nowrap">
                          <Truck className="h-3 w-3 shrink-0 text-slate-400" />
                          <span>{item.plate_no || 'N/A'}</span>
                        </div>
                        {item.driver_name && (
                          <div className="text-slate-500 text-[11px]">{item.driver_name}</div>
                        )}
                      </td>
                      <td className="py-2.5 px-4 max-w-xs">
                        <div className="font-mono font-semibold text-slate-900 whitespace-nowrap">{item.item_code}</div>
                        <div className="text-slate-500 truncate text-[11px]">{item.item_description}</div>
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums font-medium text-slate-700 whitespace-nowrap">
                        {sentQty.toLocaleString(undefined, { minimumFractionDigits: 2 })} {item.unit}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums text-emerald-600 whitespace-nowrap">
                        {recvQty.toLocaleString(undefined, { minimumFractionDigits: 2 })} {item.unit}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums font-bold whitespace-nowrap">
                        {isPending ? (
                          <span className="inline-flex items-center whitespace-nowrap rounded-md bg-amber-50 px-2 py-0.5 text-amber-700 border border-amber-200">
                            {remQty.toLocaleString(undefined, { minimumFractionDigits: 2 })} {item.unit}
                          </span>
                        ) : (
                          <span className="text-slate-400">0.00 {item.unit}</span>
                        )}
                      </td>
                      <td className="py-2.5 px-4 text-center whitespace-nowrap">
                        <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase ${getStatusBadge(item.status)}`}>
                          {item.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right whitespace-nowrap">
                        {isPending ? (
                          <Link
                            to={`/transactions/istrv?istv_id=${item.transfer_record_id}`}
                            className="inline-flex items-center gap-1 whitespace-nowrap rounded-lg bg-teal-600 px-2.5 py-1 text-xs font-semibold text-white shadow-xs hover:bg-teal-500 transition-colors"
                          >
                            <span>Receive</span>
                            <ArrowRight className="h-3 w-3" />
                          </Link>
                        ) : (
                          <span className="text-slate-400 text-[11px] whitespace-nowrap">Received</span>
                        )}
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
                {Math.min(safePage * pageSize, totalLines)} of {totalLines.toLocaleString()} in-transit lines
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

export default InTransitPage
