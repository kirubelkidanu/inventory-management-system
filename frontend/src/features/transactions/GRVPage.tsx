import React, { useState, useEffect, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import {
  ArrowDownToLine,
  Plus,
  Trash2,
  ShieldAlert,
  Loader2,
  AlertTriangle,
  ArrowLeft,
  Receipt,
} from 'lucide-react'
import { useWarehouses, useItems } from '@/features/inventory/useInventoryData'
import {
  useProjects,
  useCreateGRV,
  extractErrorMessage,
} from './useTransactionData'
import { VoucherSuccessCard } from './VoucherSuccessCard'
import type { Transaction } from '@/types'

interface GRVLineForm {
  item_id: string
  quantity: string
  unit: string
  unit_price: string
  remarks: string
}

export const GRVPage: React.FC = () => {
  const [searchParams] = useSearchParams()
  const initialWarehouseId = searchParams.get('warehouse_id') || ''
  const initialItemId = searchParams.get('item_id') || ''

  const { data: warehouses = [], isLoading: isLoadingWarehouses } = useWarehouses()
  const { data: projects = [], isLoading: isLoadingProjects } = useProjects()
  const { data: itemsData, isLoading: isLoadingItems } = useItems({ limit: 1000 })
  const items = itemsData?.items || []

  const [warehouseId, setWarehouseId] = useState(initialWarehouseId)
  const [projectId, setProjectId] = useState('')
  const [supplierName, setSupplierName] = useState('')
  const [invoiceNo, setInvoiceNo] = useState('')
  const [receivedGrvNo, setReceivedGrvNo] = useState('')
  const [storeNo, setStoreNo] = useState('')
  const [transactionDate, setTransactionDate] = useState(
    new Date().toISOString().split('T')[0]
  )
  const [remarks, setRemarks] = useState('')
  const [lines, setLines] = useState<GRVLineForm[]>([
    { item_id: initialItemId, quantity: '1', unit: 'PCS', unit_price: '0.00', remarks: '' },
  ])
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [postedTransaction, setPostedTransaction] = useState<Transaction | null>(null)

  const createGRVMutation = useCreateGRV()

  // Update initial line unit if initialItemId is provided
  useEffect(() => {
    if (initialItemId && items.length > 0) {
      const match = items.find((i) => i.id === initialItemId)
      if (match) {
        setLines((prev) => {
          const updated = [...prev]
          if (updated[0] && updated[0].item_id === initialItemId) {
            updated[0].unit = match.default_unit || 'PCS'
          }
          return updated
        })
      }
    }
  }, [initialItemId, items])

  // Update warehouse if query parameter arrives after mount
  useEffect(() => {
    if (initialWarehouseId && !warehouseId) {
      setWarehouseId(initialWarehouseId)
    }
  }, [initialWarehouseId, warehouseId])

  const handleItemChange = (idx: number, newItemId: string) => {
    const selectedItem = items.find((i) => i.id === newItemId)
    const updated = [...lines]
    updated[idx].item_id = newItemId
    if (selectedItem?.default_unit) {
      updated[idx].unit = selectedItem.default_unit
    }
    setLines(updated)
  }

  const addLine = () => {
    setLines([
      ...lines,
      { item_id: '', quantity: '1', unit: 'PCS', unit_price: '0.00', remarks: '' },
    ])
  }

  const removeLine = (idx: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== idx))
    }
  }

  // Calculate total voucher value
  const totalVoucherValue = useMemo(() => {
    return lines.reduce((sum, line) => {
      const qty = parseFloat(line.quantity) || 0
      const price = parseFloat(line.unit_price) || 0
      return sum + qty * price
    }, 0)
  }, [lines])

  const totalReceivedQuantity = useMemo(() => {
    return lines.reduce((sum, line) => {
      return sum + (parseFloat(line.quantity) || 0)
    }, 0)
  }, [lines])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!warehouseId) {
      setErrorMessage('Please select a receiving warehouse.')
      return
    }

    // Validate lines
    for (const line of lines) {
      if (!line.item_id) {
        setErrorMessage('All lines must have a selected Item SKU.')
        return
      }
      const qty = parseFloat(line.quantity)
      if (isNaN(qty) || qty <= 0) {
        setErrorMessage('All line quantities must be greater than zero.')
        return
      }
      if (!line.unit.trim()) {
        setErrorMessage('All lines must specify a unit of measurement.')
        return
      }
      const price = line.unit_price !== '' ? parseFloat(line.unit_price) : 0
      if (isNaN(price) || price < 0) {
        setErrorMessage('Line unit prices must be non-negative.')
        return
      }
    }

    // Check unique items (ADR-006)
    const itemIds = lines.map((l) => l.item_id)
    if (new Set(itemIds).size !== itemIds.length) {
      setErrorMessage('Each item can only appear once in a voucher (ADR-006). Please combine quantities.')
      return
    }

    try {
      const payload = {
        warehouse_id: warehouseId,
        project_id: projectId || null,
        transaction_date: transactionDate,
        supplier_name: supplierName.trim() || null,
        invoice_no: invoiceNo.trim() || null,
        received_grv_no: receivedGrvNo.trim() || null,
        store_no: storeNo.trim() || null,
        remarks: remarks.trim() || null,
        lines: lines.map((l) => ({
          item_id: l.item_id,
          quantity: parseFloat(l.quantity),
          unit: l.unit.trim(),
          unit_price: l.unit_price !== '' && !isNaN(parseFloat(l.unit_price)) ? parseFloat(l.unit_price) : 0,
          remarks: l.remarks.trim() || undefined,
        })),
      }

      const res = await createGRVMutation.mutateAsync(payload)
      setPostedTransaction(res)
    } catch (err) {
      setErrorMessage(extractErrorMessage(err))
    }
  }

  const handleReset = () => {
    setPostedTransaction(null)
    setSupplierName('')
    setInvoiceNo('')
    setReceivedGrvNo('')
    setStoreNo('')
    setRemarks('')
    setLines([{ item_id: '', quantity: '1', unit: 'PCS', unit_price: '0.00', remarks: '' }])
    setErrorMessage(null)
  }

  if (postedTransaction) {
    return (
      <div className="mx-auto max-w-4xl py-6">
        <VoucherSuccessCard
          transaction={postedTransaction}
          title="Goods Receiving Voucher (GRV)"
          onReset={handleReset}
        />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-sky-100 p-2.5 text-sky-700 shadow-xs">
            <ArrowDownToLine className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Goods Receiving Voucher (GRV)
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Post inbound inventory receipts from suppliers. Atomically updates balance projections and appends immutable IN ledger movements.
            </p>
          </div>
        </div>
        <Link
          to="/transactions"
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50"
        >
          <ArrowLeft className="h-4 w-4 text-slate-400" />
          <span>Back to Ledger</span>
        </Link>
      </div>

      {errorMessage && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 animate-in fade-in">
          <AlertTriangle className="h-5 w-5 shrink-0 text-red-600 mt-0.5" />
          <div>
            <span className="font-semibold">Transaction Rejected:</span> {errorMessage}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {/* Header fields */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700">Receiving Warehouse / Store *</label>
            <select
              value={warehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
              required
              disabled={isLoadingWarehouses}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-sky-500 focus:outline-hidden bg-white"
            >
              <option value="">{isLoadingWarehouses ? 'Loading warehouses...' : 'Select Warehouse...'}</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.code})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Project / Site (Optional)</label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              disabled={isLoadingProjects}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-sky-500 focus:outline-hidden bg-white"
            >
              <option value="">Select Project...</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.code})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Transaction Date *</label>
            <input
              type="date"
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
              required
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-sky-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Supplier / Vendor Name</label>
            <input
              type="text"
              value={supplierName}
              onChange={(e) => setSupplierName(e.target.value)}
              placeholder="e.g. Dangote Cement PLC"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-sky-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Supplier Invoice / Waybill #</label>
            <input
              type="text"
              value={invoiceNo}
              onChange={(e) => setInvoiceNo(e.target.value)}
              placeholder="e.g. INV-2026-990"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-sky-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Vendor GRV Ref #</label>
            <input
              type="text"
              value={receivedGrvNo}
              onChange={(e) => setReceivedGrvNo(e.target.value)}
              placeholder="e.g. GRV-VENDOR-88"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-sky-500 focus:outline-hidden"
            />
          </div>

          <div className="sm:col-span-2 lg:col-span-1">
            <label className="block text-xs font-semibold text-slate-700">Store / Bin Location</label>
            <input
              type="text"
              value={storeNo}
              onChange={(e) => setStoreNo(e.target.value)}
              placeholder="e.g. BAY-A-04"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-sky-500 focus:outline-hidden"
            />
          </div>

          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-700">Remarks / Delivery Notes</label>
            <input
              type="text"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="Optional comments regarding goods condition or transport..."
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-sky-500 focus:outline-hidden"
            />
          </div>
        </div>

        {/* Lines */}
        <div className="border-t border-slate-200 pt-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Received Line Items</h3>
              <p className="text-xs text-slate-500">Each SKU may only appear once per voucher (ADR-006)</p>
            </div>
            <button
              type="button"
              onClick={addLine}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add Line</span>
            </button>
          </div>

          <div className="mt-3 space-y-3">
            {lines.map((line, idx) => {
              const qtyNum = parseFloat(line.quantity) || 0
              const priceNum = parseFloat(line.unit_price) || 0
              const lineTotal = qtyNum * priceNum

              return (
                <div key={idx} className="flex flex-wrap lg:flex-nowrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/60 p-3.5">
                  <div className="flex-1 min-w-[200px]">
                    <label className="block text-[11px] font-medium text-slate-500">Item SKU *</label>
                    <select
                      value={line.item_id}
                      onChange={(e) => handleItemChange(idx, e.target.value)}
                      required
                      disabled={isLoadingItems}
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white focus:border-sky-500 focus:outline-hidden"
                    >
                      <option value="">{isLoadingItems ? 'Loading catalog...' : 'Select SKU...'}</option>
                      {items.map((i) => (
                        <option key={i.id} value={i.id}>
                          {i.item_code} — {i.description}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="w-24">
                    <label className="block text-[11px] font-medium text-slate-500">Quantity *</label>
                    <input
                      type="number"
                      min="0.0001"
                      step="any"
                      value={line.quantity}
                      onChange={(e) => {
                        const updated = [...lines]
                        updated[idx].quantity = e.target.value
                        setLines(updated)
                      }}
                      required
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-sky-500 focus:outline-hidden"
                    />
                  </div>

                  <div className="w-20">
                    <label className="block text-[11px] font-medium text-slate-500">Unit *</label>
                    <input
                      type="text"
                      value={line.unit}
                      onChange={(e) => {
                        const updated = [...lines]
                        updated[idx].unit = e.target.value
                        setLines(updated)
                      }}
                      required
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-sky-500 focus:outline-hidden"
                    />
                  </div>

                  <div className="w-28">
                    <label className="block text-[11px] font-medium text-slate-500">Unit Price (ETB)</label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={line.unit_price}
                      onChange={(e) => {
                        const updated = [...lines]
                        updated[idx].unit_price = e.target.value
                        setLines(updated)
                      }}
                      placeholder="0.00"
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-sky-500 focus:outline-hidden"
                    />
                  </div>

                  <div className="w-32">
                    <label className="block text-[11px] font-medium text-slate-500">Total Price (ETB)</label>
                    <div className="mt-1 flex items-center h-[34px] rounded-lg border border-slate-200 bg-slate-100/70 py-2 px-3 text-xs font-mono font-semibold text-slate-800">
                      {lineTotal.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </div>
                  </div>

                  <div className="flex-1 min-w-[130px]">
                    <label className="block text-[11px] font-medium text-slate-500">Line Remarks</label>
                    <input
                      type="text"
                      value={line.remarks}
                      onChange={(e) => {
                        const updated = [...lines]
                        updated[idx].remarks = e.target.value
                        setLines(updated)
                      }}
                      placeholder="Batch # or note"
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white focus:border-sky-500 focus:outline-hidden"
                    />
                  </div>

                  <div className="pt-4">
                    <button
                      type="button"
                      onClick={() => removeLine(idx)}
                      disabled={lines.length === 1}
                      className="rounded-lg p-2 text-slate-400 hover:bg-slate-200 hover:text-red-600 disabled:opacity-30 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Subtle summary badge/footer showing Total Voucher Value */}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-sky-100 bg-sky-50/70 p-3.5">
            <div className="flex items-center gap-2 text-xs text-sky-900">
              <Receipt className="h-4 w-4 text-sky-600" />
              <span>
                Line items: <strong>{lines.length}</strong> | Total received units: <strong>{totalReceivedQuantity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="font-medium text-slate-600">Total Voucher Value:</span>
              <span className="font-mono text-base font-bold text-sky-950">
                ETB {totalVoucherValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between border-t border-slate-200 pt-5">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <ShieldAlert className="h-4 w-4 text-emerald-600" />
            <span>Dual-write ledger entry will be posted atomically (ADR-001)</span>
          </div>
          <button
            type="submit"
            disabled={createGRVMutation.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-sky-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-sky-500 disabled:opacity-50 transition-colors"
          >
            {createGRVMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Posting GRV...</span>
              </>
            ) : (
              <span>Post GRV Transaction</span>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}

export default GRVPage
