import React, { useState } from 'react'
import {
  Scale,
  Search,
  Download,
  ArrowDownLeft,
  ArrowUpRight,
  RotateCcw,
  RefreshCw,
  Loader2,
  Calendar,
  X,
  FileText,
  Clock,
  User,
  Truck,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { useWarehouses, useCategories } from '@/features/inventory/useInventoryData'
import { useProjects, useTransaction } from '@/features/transactions/useTransactionData'
import { useTrialBalance, useExportTrialBalance, type TrialBalanceFilterParams } from './useReportData'

export const TrialBalancePage: React.FC = () => {
  // Filter states
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [projectId, setProjectId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [txType, setTxType] = useState('ALL')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  // Transaction detail inspection modal state
  const [selectedTxId, setSelectedTxId] = useState<string | null>(null)
  const { data: transactionDetails, isLoading: isLoadingTxDetails } = useTransaction(
    selectedTxId || undefined
  )

  // Dropdown options
  const { data: warehouses = [] } = useWarehouses()
  const { data: projects = [] } = useProjects()
  const { data: categories = [] } = useCategories()

  // Main trial balance query
  const queryParams: TrialBalanceFilterParams = {
    page,
    page_size: pageSize,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    warehouse_id: warehouseId || undefined,
    project_id: projectId || undefined,
    category_id: categoryId || undefined,
    transaction_type: txType !== 'ALL' ? txType : undefined,
    search: search || undefined,
  }

  const { data, isLoading, isFetching, refetch } = useTrialBalance(queryParams)
  const exportMutation = useExportTrialBalance()

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(searchInput)
    setPage(1)
  }

  const handleResetFilters = () => {
    setDateFrom('')
    setDateTo('')
    setWarehouseId('')
    setProjectId('')
    setCategoryId('')
    setTxType('ALL')
    setSearch('')
    setSearchInput('')
    setPage(1)
  }

  const handleExportExcel = () => {
    exportMutation.mutate(queryParams)
  }

  const getTypeBadge = (type: string) => {
    switch (type?.toUpperCase()) {
      case 'GRV':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200'
      case 'SIV':
        return 'bg-blue-50 text-blue-700 border-blue-200'
      case 'ISTV':
        return 'bg-purple-50 text-purple-700 border-purple-200'
      case 'ISTRV':
        return 'bg-teal-50 text-teal-700 border-teal-200'
      case 'SRV':
        return 'bg-rose-50 text-rose-700 border-rose-200'
      case 'ADJUSTMENT':
        return 'bg-amber-50 text-amber-700 border-amber-200'
      default:
        return 'bg-slate-50 text-slate-700 border-slate-200'
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total_count / pageSize)) : 1

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-2.5 text-white shadow-xs">
            <Scale className="h-6 w-6 text-sky-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Stock Trial Balance & Movement Ledger
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Authoritative chronological physical movements ledger with signed quantities and running snapshot balances.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleExportExcel}
            disabled={exportMutation.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-emerald-500 disabled:opacity-50 transition-colors"
          >
            {exportMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Exporting Excel...</span>
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                <span>Export Excel (.xlsx)</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Summary Stat Strip */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Filtered Records
            </span>
            <FileText className="h-4 w-4 text-slate-400" />
          </div>
          <p className="mt-2 text-2xl font-bold font-mono text-slate-900">
            {isLoading ? '...' : (data?.total_count || 0).toLocaleString()}
          </p>
          <span className="text-[11px] text-slate-400">Total physical movements</span>
        </div>

        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-700">
              Total Inbound Receipts (IN)
            </span>
            <ArrowDownLeft className="h-4 w-4 text-emerald-600" />
          </div>
          <p className="mt-2 text-2xl font-bold font-mono text-emerald-700">
            {isLoading ? '...' : Number(data?.total_in || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
          <span className="text-[11px] text-emerald-600/80">Credited into warehouse stores</span>
        </div>

        <div className="rounded-2xl border border-rose-200 bg-rose-50/50 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-rose-700">
              Total Outbound Issues (OUT)
            </span>
            <ArrowUpRight className="h-4 w-4 text-rose-600" />
          </div>
          <p className="mt-2 text-2xl font-bold font-mono text-rose-700">
            {isLoading ? '...' : Number(data?.total_out || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
          <span className="text-[11px] text-rose-600/80">Issued to projects or transferred</span>
        </div>
      </div>

      {/* Comprehensive Filter Toolbar */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
        {/* Transaction Type Filter Pills */}
        <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-100 pb-3">
          {[
            { id: 'ALL', label: 'All Types' },
            { id: 'GRV', label: 'GRV (Receipts)' },
            { id: 'SIV', label: 'SIV (Issues)' },
            { id: 'ISTV', label: 'ISTV (Transfers)' },
            { id: 'ISTRV', label: 'ISTRV (Received)' },
            { id: 'SRV', label: 'SRV (Returns)' },
            { id: 'ADJUSTMENT', label: 'Adjustments' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setTxType(tab.id)
                setPage(1)
              }}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                txType === tab.id
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Filter Dropdowns Grid */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <label className="block text-[11px] font-medium text-slate-500 mb-1">Date From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs focus:border-slate-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-500 mb-1">Date To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs focus:border-slate-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-500 mb-1">Warehouse</label>
            <select
              value={warehouseId}
              onChange={(e) => {
                setWarehouseId(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs focus:border-slate-500 focus:outline-hidden"
            >
              <option value="">All Warehouses</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-500 mb-1">Project / Job</label>
            <select
              value={projectId}
              onChange={(e) => {
                setProjectId(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs focus:border-slate-500 focus:outline-hidden"
            >
              <option value="">All Projects</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} — {p.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-500 mb-1">Category</label>
            <select
              value={categoryId}
              onChange={(e) => {
                setCategoryId(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs focus:border-slate-500 focus:outline-hidden"
            >
              <option value="">All Categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Search and Action Strip */}
        <div className="flex flex-wrap items-center gap-3 pt-2">
          <form onSubmit={handleSearchSubmit} className="flex-1 min-w-[260px] flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search transaction #, invoice, reference, plate, driver, or SKU..."
                className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-xs focus:border-slate-500 focus:outline-hidden"
              />
            </div>
            <button
              type="submit"
              className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-slate-800 transition-colors"
            >
              Search
            </button>
          </form>

          <button
            type="button"
            onClick={handleResetFilters}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-600 shadow-xs hover:bg-slate-50 transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5 text-slate-400" />
            <span>Reset Filters</span>
          </button>

          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Authoritative Ledger Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50/80 font-semibold text-slate-600 uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-3 px-3.5 whitespace-nowrap">Date</th>
                <th className="py-3 px-3.5 whitespace-nowrap">Transaction #</th>
                <th className="py-3 px-3 whitespace-nowrap">Type</th>
                <th className="py-3 px-3.5 whitespace-nowrap">Reference</th>
                <th className="py-3 px-3.5">SKU & Item Description</th>
                <th className="py-3 px-3 whitespace-nowrap">Category</th>
                <th className="py-3 px-3 whitespace-nowrap">Warehouse / Project</th>
                <th className="py-3 px-3 whitespace-nowrap">Logistics / Party</th>
                <th className="py-3 px-3.5 text-right whitespace-nowrap">IN (Qty)</th>
                <th className="py-3 px-3.5 text-right whitespace-nowrap">OUT (Qty)</th>
                <th className="py-3 px-3.5 text-right whitespace-nowrap">Running Bal</th>
                <th className="py-3 px-3 whitespace-nowrap">Entered By</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {isLoading ? (
                <tr>
                  <td colSpan={12} className="py-16 text-center text-slate-400">
                    <Loader2 className="mx-auto h-7 w-7 animate-spin text-slate-400 mb-2" />
                    <span>Loading Trial Balance records...</span>
                  </td>
                </tr>
              ) : !data || data.items.length === 0 ? (
                <tr>
                  <td colSpan={12} className="py-16 text-center text-slate-400">
                    <Scale className="mx-auto h-8 w-8 text-slate-300 mb-2" />
                    <p className="font-semibold text-slate-600">No stock movements found</p>
                    <p className="text-xs text-slate-400 mt-0.5">Try widening your date range or clearing filters.</p>
                  </td>
                </tr>
              ) : (
                data.items.map((row) => (
                  <tr key={row.movement_id} className="hover:bg-slate-50/75 transition-colors">
                    <td className="py-3 px-3.5 whitespace-nowrap font-mono text-slate-600">
                      {row.movement_date}
                    </td>
                    <td className="py-3 px-3.5 whitespace-nowrap font-mono font-bold text-slate-900">
                      <button
                        onClick={() => setSelectedTxId(row.transaction_id)}
                        className="hover:underline text-left text-slate-900 hover:text-sky-600 transition-colors"
                      >
                        {row.transaction_number}
                      </button>
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold ${getTypeBadge(row.transaction_type)}`}>
                        {row.transaction_type}
                      </span>
                    </td>
                    <td className="py-3 px-3.5 whitespace-nowrap font-mono text-slate-600 max-w-[130px] truncate">
                      {row.reference_number || '—'}
                    </td>
                    <td className="py-3 px-3.5 max-w-xs">
                      <div className="font-mono font-semibold text-slate-900">{row.item_code}</div>
                      <div className="text-slate-500 truncate text-[11px]">{row.item_description}</div>
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap text-slate-600">
                      {row.category_name}
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      <div className="font-medium text-slate-800">{row.warehouse_name}</div>
                      {row.project_name && (
                        <div className="text-slate-400 text-[10px]">{row.project_name}</div>
                      )}
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap text-slate-600">
                      {row.plate_no ? (
                        <div className="flex items-center gap-1 font-mono text-[11px]">
                          <Truck className="h-3 w-3 text-slate-400" />
                          <span>{row.plate_no}</span>
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-3 px-3.5 text-right font-mono font-bold text-emerald-600 whitespace-nowrap">
                      {Number(row.in_quantity) > 0
                        ? Number(row.in_quantity).toLocaleString(undefined, { minimumFractionDigits: 2 })
                        : '—'}
                    </td>
                    <td className="py-3 px-3.5 text-right font-mono font-bold text-rose-600 whitespace-nowrap">
                      {Number(row.out_quantity) > 0
                        ? Number(row.out_quantity).toLocaleString(undefined, { minimumFractionDigits: 2 })
                        : '—'}
                    </td>
                    <td className="py-3 px-3.5 text-right font-mono font-bold text-slate-900 whitespace-nowrap">
                      {row.running_balance !== null && row.running_balance !== undefined
                        ? Number(row.running_balance).toLocaleString(undefined, { minimumFractionDigits: 2 })
                        : '—'}
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap text-slate-600">
                      {row.entered_by_name}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {data && data.total_count > 0 && (
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
                Showing {Math.min((page - 1) * pageSize + 1, data.total_count)} to{' '}
                {Math.min(page * pageSize, data.total_count)} of {data.total_count.toLocaleString()} movements
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-500">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-lg border border-slate-200 bg-white p-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="rounded-lg border border-slate-200 bg-white p-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-30 transition-colors"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Transaction Inspection Modal */}
      {selectedTxId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="w-full max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div className="flex items-center gap-3">
                <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold ${getTypeBadge(transactionDetails?.transaction_type || '')}`}>
                  {transactionDetails?.transaction_type || 'VOUCHER'}
                </span>
                <div>
                  <h3 className="font-mono text-lg font-bold text-slate-900">
                    {transactionDetails?.transaction_number || 'Loading...'}
                  </h3>
                  <p className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                    <Calendar className="h-3 w-3" />
                    <span>Transaction Date: {transactionDetails?.transaction_date}</span>
                    <span>&bull;</span>
                    <Clock className="h-3 w-3" />
                    <span>Status: <strong className="uppercase">{transactionDetails?.status}</strong></span>
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedTxId(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {isLoadingTxDetails ? (
              <div className="py-12 text-center text-slate-400">
                <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400 mb-2" />
                <span>Loading transaction voucher details...</span>
              </div>
            ) : transactionDetails ? (
              <>
                {/* Metadata grid */}
                <div className="grid grid-cols-2 gap-3 rounded-xl border border-slate-100 bg-slate-50/70 p-4 text-xs sm:grid-cols-3">
                  {transactionDetails.supplier_name && (
                    <div>
                      <span className="text-slate-400 block">Supplier:</span>
                      <strong className="text-slate-800 mt-0.5 block">{transactionDetails.supplier_name}</strong>
                    </div>
                  )}
                  {transactionDetails.invoice_no && (
                    <div>
                      <span className="text-slate-400 block">Invoice #:</span>
                      <strong className="text-slate-800 font-mono mt-0.5 block">{transactionDetails.invoice_no}</strong>
                    </div>
                  )}
                  {transactionDetails.plate_no && (
                    <div>
                      <span className="text-slate-400 block">Vehicle Plate:</span>
                      <strong className="text-slate-800 mt-0.5 block">{transactionDetails.plate_no}</strong>
                    </div>
                  )}
                  {transactionDetails.driver_name && (
                    <div>
                      <span className="text-slate-400 block">Driver Name:</span>
                      <strong className="text-slate-800 mt-0.5 block">{transactionDetails.driver_name}</strong>
                    </div>
                  )}
                  {transactionDetails.project_dept && (
                    <div>
                      <span className="text-slate-400 block">Department:</span>
                      <strong className="text-slate-800 mt-0.5 block">{transactionDetails.project_dept}</strong>
                    </div>
                  )}
                  {transactionDetails.requested_no && (
                    <div>
                      <span className="text-slate-400 block">Requisition #:</span>
                      <strong className="text-slate-800 font-mono mt-0.5 block">{transactionDetails.requested_no}</strong>
                    </div>
                  )}
                  {transactionDetails.adjustment_reason && (
                    <div className="col-span-2">
                      <span className="text-slate-400 block">Adjustment Reason:</span>
                      <strong className="text-slate-800 mt-0.5 block">{transactionDetails.adjustment_reason}</strong>
                    </div>
                  )}
                  {transactionDetails.remarks && (
                    <div className="col-span-2">
                      <span className="text-slate-400 block">Remarks:</span>
                      <p className="text-slate-700 mt-0.5">{transactionDetails.remarks}</p>
                    </div>
                  )}
                </div>

                {/* Line items table */}
                <div>
                  <h4 className="text-xs font-semibold text-slate-900 mb-2">
                    Voucher Line Items ({transactionDetails.lines?.length || 0})
                  </h4>
                  <div className="overflow-hidden rounded-xl border border-slate-200">
                    <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                      <thead className="bg-slate-50 font-semibold text-slate-600">
                        <tr>
                          <th className="py-2.5 px-3">#</th>
                          <th className="py-2.5 px-3">Item ID</th>
                          <th className="py-2.5 px-3 text-right">Quantity</th>
                          <th className="py-2.5 px-3">Unit</th>
                          <th className="py-2.5 px-3">Remarks</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-slate-700">
                        {transactionDetails.lines?.map((l, idx) => (
                          <tr key={l.id || idx}>
                            <td className="py-2 px-3 font-mono text-slate-400">{l.line_number || idx + 1}</td>
                            <td className="py-2 px-3 font-mono font-medium text-slate-800">{l.item_id}</td>
                            <td className="py-2 px-3 text-right font-mono font-bold text-slate-900">
                              {Number(l.quantity).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </td>
                            <td className="py-2 px-3 font-mono text-slate-600">{l.unit}</td>
                            <td className="py-2 px-3 text-slate-500">{l.remarks || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Signatories */}
                {(transactionDetails.issued_by_name ||
                  transactionDetails.checked_by_name ||
                  transactionDetails.received_by_name ||
                  transactionDetails.approved_by_name) && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-3.5">
                    <h5 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
                      <User className="h-3.5 w-3.5" />
                      <span>Signatories</span>
                    </h5>
                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-700 sm:grid-cols-4">
                      <div>Issued: <strong>{transactionDetails.issued_by_name || '—'}</strong></div>
                      <div>Checked: <strong>{transactionDetails.checked_by_name || '—'}</strong></div>
                      <div>Received: <strong>{transactionDetails.received_by_name || '—'}</strong></div>
                      <div>Approved: <strong>{transactionDetails.approved_by_name || '—'}</strong></div>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="py-8 text-center text-sm text-slate-500">
                Transaction details not found.
              </div>
            )}

            <div className="flex justify-end border-t border-slate-100 pt-3">
              <button
                onClick={() => setSelectedTxId(null)}
                className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default TrialBalancePage
