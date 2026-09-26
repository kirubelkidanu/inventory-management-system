import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Truck,
  PackageOpen,
  Undo2,
  Sliders,
  Search,
  RefreshCw,
  Eye,
  X,
  FileText,
  Calendar,
  Layers,
  MapPin,
  Clock,
  User,
} from 'lucide-react'
import { useWarehouses } from '@/features/inventory/useInventoryData'
import { useTransactions } from './useTransactionData'
import type { Transaction } from '@/types'

export const TransactionsListPage: React.FC = () => {
  const [filterType, setFilterType] = useState('ALL')
  const [warehouseId, setWarehouseId] = useState('')
  const [search, setSearch] = useState('')
  const [selectedTx, setSelectedTx] = useState<Transaction | null>(null)

  const { data: warehouses = [] } = useWarehouses()
  const {
    data: transactions = [],
    isLoading,
    isFetching,
    refetch,
  } = useTransactions({
    transaction_type: filterType,
    warehouse_id: warehouseId || undefined,
    search: search || undefined,
    limit: 100,
  })

  const getStatusBadge = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'POSTED':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200'
      case 'IN_TRANSIT':
        return 'bg-amber-50 text-amber-700 border-amber-200'
      case 'PARTIALLY_RECEIVED':
        return 'bg-teal-50 text-teal-700 border-teal-200'
      case 'COMPLETED':
        return 'bg-blue-50 text-blue-700 border-blue-200'
      case 'DRAFT':
        return 'bg-slate-100 text-slate-700 border-slate-200'
      default:
        return 'bg-slate-50 text-slate-600 border-slate-200'
    }
  }

  const getTypeBadge = (type: string) => {
    switch (type?.toUpperCase()) {
      case 'GRV':
        return 'bg-sky-50 text-sky-700 border-sky-200'
      case 'SIV':
        return 'bg-indigo-50 text-indigo-700 border-indigo-200'
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

  const warehouseMap = new Map(warehouses.map((w) => [w.id, w.name]))

  const formatLocation = (tx: Transaction) => {
    if (tx.source_warehouse_id && tx.destination_warehouse_id) {
      const src = warehouseMap.get(tx.source_warehouse_id) || 'Origin WH'
      const dst = warehouseMap.get(tx.destination_warehouse_id) || 'Dest WH'
      return `${src} -> ${dst}`
    }
    if (tx.warehouse_id) {
      return warehouseMap.get(tx.warehouse_id) || 'Store Location'
    }
    return 'Central Warehouse'
  }

  const formatPartyOrRef = (tx: Transaction) => {
    if (tx.supplier_name) return tx.supplier_name
    if (tx.project_dept) return `Dept: ${tx.project_dept}`
    if (tx.plate_no) return `Veh: ${tx.plate_no}${tx.driver_name ? ` (${tx.driver_name})` : ''}`
    if (tx.adjustment_reason) return tx.adjustment_reason
    if (tx.remarks) return tx.remarks
    return '—'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Transaction Ledger & Vouchers
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Authoritative history of all dual-written inventory vouchers, store issuances, receipts, and transfers.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/transactions/grv"
            className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-sky-500 transition-colors"
          >
            <ArrowDownToLine className="h-3.5 w-3.5" />
            <span>+ GRV</span>
          </Link>
          <Link
            to="/transactions/siv"
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-indigo-500 transition-colors"
          >
            <ArrowUpFromLine className="h-3.5 w-3.5" />
            <span>+ SIV</span>
          </Link>
          <Link
            to="/transactions/istv"
            className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-purple-500 transition-colors"
          >
            <Truck className="h-3.5 w-3.5" />
            <span>+ ISTV</span>
          </Link>
          <Link
            to="/transactions/istrv"
            className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-teal-500 transition-colors"
          >
            <PackageOpen className="h-3.5 w-3.5" />
            <span>+ ISTRV</span>
          </Link>
          <Link
            to="/transactions/srv"
            className="inline-flex items-center gap-1.5 rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-rose-500 transition-colors"
          >
            <Undo2 className="h-3.5 w-3.5" />
            <span>+ SRV</span>
          </Link>
          <Link
            to="/transactions/adjustment"
            className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-amber-500 transition-colors"
          >
            <Sliders className="h-3.5 w-3.5" />
            <span>+ Adjust</span>
          </Link>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        {/* Type pills */}
        <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-100 pb-3">
          {[
            { id: 'ALL', label: 'All Vouchers' },
            { id: 'GRV', label: 'GRV (Receipts)' },
            { id: 'SIV', label: 'SIV (Issues)' },
            { id: 'ISTV', label: 'ISTV (Dispatches)' },
            { id: 'ISTRV', label: 'ISTRV (Received)' },
            { id: 'SRV', label: 'SRV (Returns)' },
            { id: 'ADJUSTMENT', label: 'Adjustments' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilterType(tab.id)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                filterType === tab.id
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
              placeholder="Search voucher #, reference, supplier, plate, driver..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-xs focus:border-slate-500 focus:outline-hidden"
            />
          </div>

          <div className="w-56">
            <select
              value={warehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
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

          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50/75 text-xs font-semibold text-slate-600">
              <tr>
                <th className="py-3 px-4">Voucher Number</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Warehouse / Routing</th>
                <th className="py-3 px-4">Party / Reference</th>
                <th className="py-3 px-4 text-center">Items</th>
                <th className="py-3 px-4 text-center">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400">
                    <RefreshCw className="mx-auto h-6 w-6 animate-spin text-slate-400 mb-2" />
                    <span>Loading transaction history...</span>
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400">
                    <FileText className="mx-auto h-8 w-8 text-slate-300 mb-2" />
                    <p className="font-medium text-slate-600">No transactions found matching criteria</p>
                    <p className="mt-1 text-xs text-slate-400">Create a new voucher above to initiate stock changes.</p>
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-900">
                      <button
                        onClick={() => setSelectedTx(tx)}
                        className="hover:underline text-left text-slate-900 hover:text-sky-600 transition-colors"
                      >
                        {tx.transaction_number}
                      </button>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold ${getTypeBadge(tx.transaction_type)}`}>
                        {tx.transaction_type}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 whitespace-nowrap">
                      {tx.transaction_date}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-800">
                      {formatLocation(tx)}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 max-w-xs truncate">
                      {formatPartyOrRef(tx)}
                    </td>
                    <td className="py-3.5 px-4 text-center font-mono">
                      {tx.lines?.length || 0}
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${getStatusBadge(tx.status)}`}>
                        {tx.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => setSelectedTx(tx)}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-xs hover:bg-slate-50 transition-colors"
                      >
                        <Eye className="h-3.5 w-3.5 text-slate-500" />
                        <span>Details</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Voucher Detail Modal */}
      {selectedTx && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="w-full max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div className="flex items-center gap-3">
                <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold ${getTypeBadge(selectedTx.transaction_type)}`}>
                  {selectedTx.transaction_type}
                </span>
                <div>
                  <h3 className="font-mono text-lg font-bold text-slate-900">
                    {selectedTx.transaction_number}
                  </h3>
                  <p className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                    <Calendar className="h-3 w-3" />
                    <span>Transaction Date: {selectedTx.transaction_date}</span>
                    <span>&bull;</span>
                    <Clock className="h-3 w-3" />
                    <span>Status: <strong className="uppercase">{selectedTx.status}</strong></span>
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedTx(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Metadata grid */}
            <div className="grid grid-cols-2 gap-3 rounded-xl border border-slate-100 bg-slate-50/70 p-4 text-xs sm:grid-cols-3">
              <div>
                <span className="text-slate-400 block">Warehouse / Store:</span>
                <strong className="text-slate-800 flex items-center gap-1 mt-0.5">
                  <MapPin className="h-3 w-3 text-slate-500" />
                  {formatLocation(selectedTx)}
                </strong>
              </div>
              {selectedTx.supplier_name && (
                <div>
                  <span className="text-slate-400 block">Supplier:</span>
                  <strong className="text-slate-800 mt-0.5 block">{selectedTx.supplier_name}</strong>
                </div>
              )}
              {selectedTx.invoice_no && (
                <div>
                  <span className="text-slate-400 block">Invoice #:</span>
                  <strong className="text-slate-800 font-mono mt-0.5 block">{selectedTx.invoice_no}</strong>
                </div>
              )}
              {selectedTx.plate_no && (
                <div>
                  <span className="text-slate-400 block">Vehicle Plate:</span>
                  <strong className="text-slate-800 mt-0.5 block">{selectedTx.plate_no}</strong>
                </div>
              )}
              {selectedTx.driver_name && (
                <div>
                  <span className="text-slate-400 block">Driver Name:</span>
                  <strong className="text-slate-800 mt-0.5 block">{selectedTx.driver_name}</strong>
                </div>
              )}
              {selectedTx.project_dept && (
                <div>
                  <span className="text-slate-400 block">Department:</span>
                  <strong className="text-slate-800 mt-0.5 block">{selectedTx.project_dept}</strong>
                </div>
              )}
              {selectedTx.requested_no && (
                <div>
                  <span className="text-slate-400 block">Requisition #:</span>
                  <strong className="text-slate-800 font-mono mt-0.5 block">{selectedTx.requested_no}</strong>
                </div>
              )}
              {selectedTx.adjustment_reason && (
                <div className="col-span-2">
                  <span className="text-slate-400 block">Adjustment Reason:</span>
                  <strong className="text-slate-800 mt-0.5 block">{selectedTx.adjustment_reason}</strong>
                </div>
              )}
              {selectedTx.remarks && (
                <div className="col-span-2">
                  <span className="text-slate-400 block">Voucher Remarks:</span>
                  <p className="text-slate-700 mt-0.5">{selectedTx.remarks}</p>
                </div>
              )}
            </div>

            {/* Line items table */}
            <div>
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-900 mb-2">
                <Layers className="h-4 w-4 text-slate-500" />
                <span>Voucher Line Items ({selectedTx.lines?.length || 0})</span>
              </div>
              <div className="overflow-hidden rounded-xl border border-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                  <thead className="bg-slate-50 font-semibold text-slate-600">
                    <tr>
                      <th className="py-2.5 px-3">#</th>
                      <th className="py-2.5 px-3">Item ID</th>
                      <th className="py-2.5 px-3 text-right">Quantity</th>
                      <th className="py-2.5 px-3">Unit</th>
                      <th className="py-2.5 px-3">Line Remarks</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {selectedTx.lines && selectedTx.lines.length > 0 ? (
                      selectedTx.lines.map((l, idx) => (
                        <tr key={l.id || idx}>
                          <td className="py-2 px-3 font-mono text-slate-400">{l.line_number || idx + 1}</td>
                          <td className="py-2 px-3 font-mono font-medium text-slate-800">{l.item_id}</td>
                          <td className="py-2 px-3 text-right font-mono font-bold text-slate-900">
                            {Number(l.quantity).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </td>
                          <td className="py-2 px-3 font-mono text-slate-600">{l.unit}</td>
                          <td className="py-2 px-3 text-slate-500">{l.remarks || '—'}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} className="py-4 text-center text-slate-400">
                          No line items recorded on this transaction header
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Signatory / Audit info */}
            {(selectedTx.issued_by_name || selectedTx.checked_by_name || selectedTx.received_by_name || selectedTx.approved_by_name) && (
              <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-3.5">
                <h5 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
                  <User className="h-3.5 w-3.5" />
                  <span>Document Signatories</span>
                </h5>
                <div className="grid grid-cols-2 gap-2 text-xs text-slate-700 sm:grid-cols-4">
                  <div>Issued By: <strong>{selectedTx.issued_by_name || '—'}</strong></div>
                  <div>Checked By: <strong>{selectedTx.checked_by_name || '—'}</strong></div>
                  <div>Received By: <strong>{selectedTx.received_by_name || '—'}</strong></div>
                  <div>Approved By: <strong>{selectedTx.approved_by_name || '—'}</strong></div>
                </div>
              </div>
            )}

            <div className="flex justify-end border-t border-slate-100 pt-3">
              <button
                onClick={() => setSelectedTx(null)}
                className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 transition-colors"
              >
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default TransactionsListPage
