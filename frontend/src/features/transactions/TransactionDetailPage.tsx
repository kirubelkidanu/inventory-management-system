import React, { useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  Calendar,
  Layers,
  MapPin,
  Clock,
  User,
  X,
  AlertCircle,
  RotateCw,
} from 'lucide-react'
import api from '@/lib/api'
import { useWarehouses } from '@/features/inventory/useInventoryData'
import type { Transaction } from '@/types'

interface TransactionDetailPageProps {
  transaction?: Transaction | null
  onClose?: () => void
}

export const TransactionDetailPage: React.FC<TransactionDetailPageProps> = ({
  transaction: propTransaction,
  onClose,
}) => {
  const { id } = useParams<{ id: string }>()

  const { data: warehouses = [] } = useWarehouses()
  const warehouseMap = useMemo(() => new Map(warehouses.map((w) => [w.id, w.name])), [warehouses])

  // Fetch transaction if loaded via route /transactions/:id
  const {
    data: fetchedTransaction,
    isLoading,
    isError,
  } = useQuery<Transaction>({
    queryKey: ['transaction', id],
    queryFn: async () => {
      const response = await api.get<Transaction>(`/transactions/${id}`)
      return response.data
    },
    enabled: !propTransaction && !!id,
  })

  const tx = propTransaction || fetchedTransaction

  const isGRV = useMemo(() => {
    if (!tx) return false
    return (
      tx.transaction_type?.toUpperCase() === 'GRV' ||
      (tx.lines || []).some(
        (l) => l.unit_price !== undefined && l.unit_price !== null && Number(l.unit_price) > 0
      )
    )
  }, [tx])

  const totalVoucherValue = useMemo(() => {
    if (!tx?.lines) return 0
    return tx.lines.reduce((sum, l) => {
      const q = Number(l.quantity) || 0
      const p = Number(l.unit_price) || 0
      return sum + q * p
    }, 0)
  }, [tx?.lines])

  const totalQuantity = useMemo(() => {
    if (!tx?.lines) return 0
    return tx.lines.reduce((sum, l) => sum + (Number(l.quantity) || 0), 0)
  }, [tx?.lines])

  const getStatusBadge = (status?: string) => {
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

  const getTypeBadge = (type?: string) => {
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

  const formatLocation = (t: Transaction) => {
    if (t.source_warehouse_id && t.destination_warehouse_id) {
      const src = warehouseMap.get(t.source_warehouse_id) || 'Origin WH'
      const dst = warehouseMap.get(t.destination_warehouse_id) || 'Dest WH'
      return `${src} -> ${dst}`
    }
    if (t.warehouse_id) {
      return warehouseMap.get(t.warehouse_id) || 'Store Location'
    }
    return 'Central Warehouse'
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-slate-500">
        <RotateCw className="h-8 w-8 animate-spin text-sky-500 mb-2" />
        <span className="text-sm font-medium">Loading transaction details...</span>
      </div>
    )
  }

  if (isError || !tx) {
    return (
      <div className="mx-auto max-w-3xl rounded-2xl border border-red-200 bg-red-50 p-6 text-center text-red-800">
        <AlertCircle className="mx-auto h-8 w-8 text-red-600 mb-2" />
        <h2 className="text-lg font-bold">Transaction Not Found</h2>
        <p className="mt-1 text-sm text-red-600">The requested voucher record could not be retrieved from the ledger.</p>
        <div className="mt-4">
          <Link
            to="/transactions"
            className="inline-flex items-center gap-1.5 rounded-lg bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-xs border border-slate-200 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Return to Transactions</span>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {onClose ? (
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500 hover:bg-slate-50"
            >
              <X className="h-4 w-4" />
            </button>
          ) : (
            <Link
              to="/transactions"
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50"
            >
              <ArrowLeft className="h-4 w-4 text-slate-400" />
              <span>Back to Transactions</span>
            </Link>
          )}
          <div>
            <div className="flex items-center gap-2">
              <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-semibold ${getTypeBadge(tx.transaction_type)}`}>
                {tx.transaction_type}
              </span>
              <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${getStatusBadge(tx.status)}`}>
                {tx.status}
              </span>
            </div>
            <h1 className="mt-1 font-mono text-xl font-bold text-slate-900 sm:text-2xl">
              {tx.transaction_number}
            </h1>
          </div>
        </div>

        {totalVoucherValue > 0 && (
          <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-2 text-right">
            <span className="text-[11px] font-medium text-sky-700">Total Voucher Value</span>
            <p className="font-mono text-lg font-bold text-sky-950">
              ETB {totalVoucherValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>
        )}
      </div>

      {/* Summary Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
        <div className="grid grid-cols-2 gap-4 text-xs sm:grid-cols-4">
          <div>
            <span className="text-slate-400 block">Transaction Date</span>
            <strong className="text-slate-800 flex items-center gap-1 mt-0.5">
              <Calendar className="h-3.5 w-3.5 text-slate-400" />
              {tx.transaction_date}
            </strong>
          </div>
          <div>
            <span className="text-slate-400 block">Warehouse / Store</span>
            <strong className="text-slate-800 flex items-center gap-1 mt-0.5">
              <MapPin className="h-3.5 w-3.5 text-slate-400" />
              {formatLocation(tx)}
            </strong>
          </div>
          <div>
            <span className="text-slate-400 block">Posted At</span>
            <strong className="text-slate-800 flex items-center gap-1 mt-0.5">
              <Clock className="h-3.5 w-3.5 text-slate-400" />
              {tx.posted_at ? new Date(tx.posted_at).toLocaleDateString() : tx.transaction_date}
            </strong>
          </div>
          <div>
            <span className="text-slate-400 block">Line Items Count</span>
            <strong className="text-slate-800 flex items-center gap-1 mt-0.5">
              <Layers className="h-3.5 w-3.5 text-slate-400" />
              {tx.lines?.length || 0} line(s)
            </strong>
          </div>

          {tx.supplier_name && (
            <div className="col-span-2">
              <span className="text-slate-400 block">Supplier / Vendor:</span>
              <strong className="text-slate-800 mt-0.5 block">{tx.supplier_name}</strong>
            </div>
          )}
          {tx.invoice_no && (
            <div>
              <span className="text-slate-400 block">Invoice / Waybill #:</span>
              <strong className="text-slate-800 font-mono mt-0.5 block">{tx.invoice_no}</strong>
            </div>
          )}
          {tx.received_grv_no && (
            <div>
              <span className="text-slate-400 block">Vendor GRV Ref #:</span>
              <strong className="text-slate-800 font-mono mt-0.5 block">{tx.received_grv_no}</strong>
            </div>
          )}
          {tx.store_no && (
            <div>
              <span className="text-slate-400 block">Store / Bin Location:</span>
              <strong className="text-slate-800 mt-0.5 block">{tx.store_no}</strong>
            </div>
          )}
          {tx.plate_no && (
            <div>
              <span className="text-slate-400 block">Vehicle Plate:</span>
              <strong className="text-slate-800 mt-0.5 block">{tx.plate_no}</strong>
            </div>
          )}
          {tx.driver_name && (
            <div>
              <span className="text-slate-400 block">Driver Name:</span>
              <strong className="text-slate-800 mt-0.5 block">{tx.driver_name}</strong>
            </div>
          )}
          {tx.project_dept && (
            <div>
              <span className="text-slate-400 block">Department:</span>
              <strong className="text-slate-800 mt-0.5 block">{tx.project_dept}</strong>
            </div>
          )}
          {tx.requested_no && (
            <div>
              <span className="text-slate-400 block">Requisition #:</span>
              <strong className="text-slate-800 font-mono mt-0.5 block">{tx.requested_no}</strong>
            </div>
          )}
          {tx.adjustment_reason && (
            <div className="col-span-2">
              <span className="text-slate-400 block">Adjustment Reason:</span>
              <strong className="text-slate-800 mt-0.5 block">{tx.adjustment_reason}</strong>
            </div>
          )}
          {tx.remarks && (
            <div className="col-span-2">
              <span className="text-slate-400 block">Voucher Remarks:</span>
              <p className="text-slate-700 mt-0.5">{tx.remarks}</p>
            </div>
          )}
        </div>

        {/* Line Items Table */}
        <div className="border-t border-slate-200 pt-5 space-y-3">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-900">
            <div className="flex items-center gap-1.5">
              <Layers className="h-4 w-4 text-slate-500" />
              <span>Voucher Line Items ({tx.lines?.length || 0})</span>
            </div>
            <span className="text-slate-500">
              Total Quantity: <strong className="text-slate-800">{totalQuantity.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
            </span>
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 font-semibold text-slate-600">
                <tr>
                  <th className="py-2.5 px-3">#</th>
                  <th className="py-2.5 px-3">Item ID</th>
                  <th className="py-2.5 px-3 text-right">Quantity</th>
                  <th className="py-2.5 px-3">Unit</th>
                  {isGRV && (
                    <>
                      <th className="py-2.5 px-3 text-right">Unit Price (ETB)</th>
                      <th className="py-2.5 px-3 text-right">Total Price (ETB)</th>
                    </>
                  )}
                  <th className="py-2.5 px-3">Line Remarks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {tx.lines && tx.lines.length > 0 ? (
                  tx.lines.map((l, idx) => {
                    const qty = Number(l.quantity) || 0
                    const price = l.unit_price !== undefined && l.unit_price !== null ? Number(l.unit_price) : 0
                    const lineTotal = l.total_price !== undefined && l.total_price !== null ? Number(l.total_price) : qty * price

                    return (
                      <tr key={l.id || idx} className="hover:bg-slate-50/70 transition-colors">
                        <td className="py-2.5 px-3 font-mono text-slate-400">{l.line_number || idx + 1}</td>
                        <td className="py-2.5 px-3 font-mono font-medium text-slate-800">{l.item_id}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold text-slate-900">
                          {qty.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-600">{l.unit}</td>
                        {isGRV && (
                          <>
                            <td className="py-2.5 px-3 text-right font-mono text-slate-700">
                              {price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </td>
                            <td className="py-2.5 px-3 text-right font-mono font-bold text-emerald-700">
                              {lineTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </td>
                          </>
                        )}
                        <td className="py-2.5 px-3 text-slate-500">{l.remarks || '—'}</td>
                      </tr>
                    )
                  })
                ) : (
                  <tr>
                    <td colSpan={isGRV ? 7 : 5} className="py-6 text-center text-slate-400">
                      No line items recorded on this transaction voucher
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {isGRV && (
            <div className="flex items-center justify-between rounded-xl border border-sky-100 bg-sky-50/70 p-3.5 text-xs">
              <span className="font-semibold text-slate-700">Total Voucher Value (ETB):</span>
              <span className="font-mono text-base font-bold text-sky-950">
                ETB {totalVoucherValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          )}
        </div>

        {/* Signatory card */}
        {(tx.issued_by_name || tx.checked_by_name || tx.received_by_name || tx.approved_by_name) && (
          <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
            <h5 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2.5 flex items-center gap-1.5">
              <User className="h-3.5 w-3.5" />
              <span>Document Signatories</span>
            </h5>
            <div className="grid grid-cols-2 gap-3 text-xs text-slate-700 sm:grid-cols-4">
              <div>Issued By: <strong className="block text-slate-900 mt-0.5">{tx.issued_by_name || '—'}</strong></div>
              <div>Checked By: <strong className="block text-slate-900 mt-0.5">{tx.checked_by_name || '—'}</strong></div>
              <div>Received By: <strong className="block text-slate-900 mt-0.5">{tx.received_by_name || '—'}</strong></div>
              <div>Approved By: <strong className="block text-slate-900 mt-0.5">{tx.approved_by_name || '—'}</strong></div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default TransactionDetailPage
