import React, { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Undo2,
  Plus,
  Trash2,
  ShieldAlert,
  Loader2,
  AlertTriangle,
  ArrowLeft,
} from 'lucide-react'
import { useWarehouses } from '@/features/inventory/useInventoryData'
import { ItemCombobox } from '@/components/ItemCombobox'
import {
  useProjects,
  useTransactions,
  useCreateSRV,
  useSIVReturnableItems,
  extractErrorMessage,
} from './useTransactionData'
import { VoucherSuccessCard } from './VoucherSuccessCard'
import type { Item, Transaction } from '@/types'

interface SRVLineForm {
  item_id: string
  item_code: string
  item_description: string
  issued_quantity: number
  remaining_returnable_quantity: number
  quantity: string
  unit: string
  unit_price: number | null
  remarks: string
}

export const SRVPage: React.FC = () => {
  const { data: warehouses = [], isLoading: isLoadingWarehouses } = useWarehouses()
  const { data: projects = [], isLoading: isLoadingProjects } = useProjects()

  // Load prior SIV transactions to enable fast reference selection
  const { data: sivTransactions = [], isLoading: isLoadingSIVs } = useTransactions({
    transaction_type: 'SIV',
    limit: 50,
  })

  const [referenceSivId, setReferenceSivId] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [projectId, setProjectId] = useState('')
  const [transactionDate, setTransactionDate] = useState(
    new Date().toISOString().split('T')[0]
  )
  const [remarks, setRemarks] = useState('')
  const [lines, setLines] = useState<SRVLineForm[]>([])

  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [postedTransaction, setPostedTransaction] = useState<Transaction | null>(null)

  const createSRVMutation = useCreateSRV()

  // Query returnable items for selected SIV
  const {
    data: returnableData,
    isLoading: isLoadingReturnable
  } = useSIVReturnableItems(referenceSivId)

  // Handle selecting an SIV from the list
  const handleSelectSIV = (sivId: string) => {
    setReferenceSivId(sivId)
    setErrorMessage(null)
  }

  // When returnable data is fetched, auto-populate warehouse, project, and lines
  useEffect(() => {
    if (returnableData) {
      if (returnableData.warehouse_id) {
        setWarehouseId(returnableData.warehouse_id)
      }
      if (returnableData.project_id) {
        setProjectId(returnableData.project_id)
      }

      if (returnableData.lines && returnableData.lines.length > 0) {
        // Pre-populate with items that have remaining returnable quantity
        const eligible = returnableData.lines.map((l) => {
          const avail = Number(l.remaining_returnable_quantity) || 0
          const issued = Number(l.issued_quantity) || 0
          const price = l.unit_price !== undefined && l.unit_price !== null ? Number(l.unit_price) : null
          return {
            item_id: l.item_id,
            item_code: l.item_code || '',
            item_description: l.description || '',
            issued_quantity: issued,
            remaining_returnable_quantity: avail,
            // Default to remaining returnable quantity or 1
            quantity: String(avail > 0 ? (avail >= 1 ? 1 : avail) : 0),
            unit: l.unit || 'PCS',
            unit_price: price,
            remarks: `Surplus return from ${returnableData.transaction_number}`,
          }
        })
        setLines(eligible)
      } else {
        setLines([])
      }
    }
  }, [returnableData])

  const handleLineQtyChange = (idx: number, val: string) => {
    const updated = [...lines]
    updated[idx].quantity = val
    setLines(updated)
  }

  const handleLinePriceChange = (idx: number, val: string) => {
    const updated = [...lines]
    const p = parseFloat(val)
    updated[idx].unit_price = isNaN(p) ? null : p
    setLines(updated)
  }

  const handleLineRemarksChange = (idx: number, val: string) => {
    const updated = [...lines]
    updated[idx].remarks = val
    setLines(updated)
  }

  const handleItemChange = (idx: number, newItemId: string, item?: Item) => {
    const updated = [...lines]
    updated[idx].item_id = newItemId
    if (item) {
      updated[idx].item_code = item.item_code || ''
      updated[idx].item_description = item.description || ''
      if (item.default_unit) {
        updated[idx].unit = item.default_unit
      }
      if (item.latest_unit_price) {
        updated[idx].unit_price = Number(item.latest_unit_price)
      }
    }
    setLines(updated)
  }

  const addLine = () => {
    setLines([
      ...lines,
      {
        item_id: '',
        item_code: '',
        item_description: '',
        issued_quantity: 0,
        remaining_returnable_quantity: 999999,
        quantity: '1',
        unit: 'PCS',
        unit_price: null,
        remarks: '',
      },
    ])
  }

  const removeLine = (idx: number) => {
    setLines(lines.filter((_, i) => i !== idx))
  }

  // Summary calculations
  const totalReturnLines = lines.length
  const totalReturnedQuantity = useMemo(() => {
    return lines.reduce((sum, l) => sum + (parseFloat(l.quantity) || 0), 0)
  }, [lines])

  const totalReturnedValuation = useMemo(() => {
    return lines.reduce((sum, l) => {
      const q = parseFloat(l.quantity) || 0
      const p = l.unit_price || 0
      return sum + q * p
    }, 0)
  }, [lines])

  // Over-return and validation checks
  const hasOverReturn = useMemo(() => {
    return lines.some((l) => {
      const q = parseFloat(l.quantity) || 0
      return l.remaining_returnable_quantity > 0 && q > l.remaining_returnable_quantity
    })
  }, [lines])

  const hasInvalidQty = useMemo(() => {
    return lines.some((l) => {
      const q = parseFloat(l.quantity)
      return isNaN(q) || q <= 0
    })
  }, [lines])

  const isSubmitDisabled =
    !referenceSivId.trim() ||
    !warehouseId ||
    lines.length === 0 ||
    hasOverReturn ||
    hasInvalidQty ||
    totalReturnedQuantity <= 0 ||
    createSRVMutation.isPending

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!referenceSivId.trim()) {
      setErrorMessage('A referenced Store Issue Voucher (SIV) ID is required.')
      return
    }

    if (!warehouseId) {
      setErrorMessage('Please select a receiving warehouse.')
      return
    }

    if (lines.length === 0) {
      setErrorMessage('At least one item line must be returned.')
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
        setErrorMessage('All return quantities must be greater than zero.')
        return
      }
      if (line.remaining_returnable_quantity > 0 && qty > line.remaining_returnable_quantity) {
        setErrorMessage(
          `Return quantity (${qty}) exceeds remaining returnable quantity (${line.remaining_returnable_quantity}) for item ${line.item_code || line.item_id}. Over-returning is strictly prohibited.`
        )
        return
      }
      if (!line.unit.trim()) {
        setErrorMessage('All lines must specify a unit of measurement.')
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
        reference_siv_id: referenceSivId.trim(),
        warehouse_id: warehouseId,
        project_id: projectId || null,
        transaction_date: transactionDate,
        remarks: remarks.trim() || null,
        lines: lines.map((l) => ({
          item_id: l.item_id,
          quantity: parseFloat(l.quantity),
          unit: l.unit.trim(),
          unit_price: l.unit_price,
          remarks: l.remarks.trim() || undefined,
        })),
      }

      const res = await createSRVMutation.mutateAsync(payload)
      setPostedTransaction(res)
    } catch (err) {
      setErrorMessage(extractErrorMessage(err))
    }
  }

  const handleReset = () => {
    setPostedTransaction(null)
    setReferenceSivId('')
    setWarehouseId('')
    setProjectId('')
    setRemarks('')
    setLines([])
    setErrorMessage(null)
  }

  if (postedTransaction) {
    return (
      <div className="mx-auto max-w-4xl py-6">
        <VoucherSuccessCard
          transaction={postedTransaction}
          title="Store Return Voucher (SRV)"
          onReset={handleReset}
        />
      </div>
    )
  }

  const selectedSIV = sivTransactions.find((s) => s.id === referenceSivId)

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-rose-100 p-2.5 text-rose-700 shadow-xs">
            <Undo2 className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Store Return Voucher (SRV)
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Process returns of unused/surplus items back to inventory against an originating SIV. Auto-populates issued items, inherits unit prices, and enforces strict over-return prevention.
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

      {hasOverReturn && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs font-medium text-amber-900">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
          <span>
            One or more line items have return quantities exceeding remaining returnable balances. Please adjust return quantities before posting.
          </span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-700">Reference Prior SIV Voucher *</label>
            <select
              value={referenceSivId}
              onChange={(e) => handleSelectSIV(e.target.value)}
              required
              disabled={isLoadingSIVs}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-rose-500 focus:outline-hidden"
            >
              <option value="">
                {isLoadingSIVs
                  ? 'Loading SIV vouchers...'
                  : sivTransactions.length === 0
                  ? 'No prior SIV vouchers found (enter ID manually)'
                  : 'Select prior SIV voucher to auto-populate items...'}
              </option>
              {sivTransactions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.transaction_number} ({s.transaction_date}) {s.project_dept ? `— ${s.project_dept}` : ''} {s.requested_no ? `[Req: ${s.requested_no}]` : ''}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Return Date *</label>
            <input
              type="date"
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
              required
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-rose-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Receiving Warehouse *</label>
            <select
              value={warehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
              required
              disabled={isLoadingWarehouses}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-rose-500 focus:outline-hidden"
            >
              <option value="">Select Receiving Warehouse...</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Credited Project</label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              disabled={isLoadingProjects}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-rose-500 focus:outline-hidden"
            >
              <option value="">General / Unassigned</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} — {p.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Manual SIV ID (UUID fallback)</label>
            <input
              type="text"
              value={referenceSivId}
              onChange={(e) => setReferenceSivId(e.target.value)}
              placeholder="Paste SIV UUID if not listed above"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm font-mono text-xs focus:border-rose-500 focus:outline-hidden"
            />
          </div>

          <div className="sm:col-span-3">
            <label className="block text-xs font-semibold text-slate-700">Return Reason / Justification</label>
            <input
              type="text"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="e.g. Unopened surplus cement and rebar returned after foundation completion"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-rose-500 focus:outline-hidden"
            />
          </div>
        </div>

        {/* Selected SIV summary banner */}
        {(selectedSIV || returnableData) && (
          <div className="rounded-xl border border-rose-200 bg-rose-50/50 p-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-rose-800">
                Referenced SIV: {returnableData?.transaction_number || selectedSIV?.transaction_number}
              </h4>
              {isLoadingReturnable && (
                <div className="flex items-center gap-1.5 text-xs text-rose-700">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Loading returnable lines...</span>
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs text-rose-900 sm:grid-cols-4">
              <div>
                <span className="text-rose-600 block">Issued Date:</span>
                <strong>{returnableData?.transaction_date || selectedSIV?.transaction_date}</strong>
              </div>
              <div>
                <span className="text-rose-600 block">Department / Project:</span>
                <strong>{selectedSIV?.project_dept || 'General'}</strong>
              </div>
              <div>
                <span className="text-rose-600 block">SIV Ref #:</span>
                <strong>{returnableData?.siv_no || selectedSIV?.siv_no || selectedSIV?.transaction_number || 'N/A'}</strong>
              </div>
              <div>
                <span className="text-rose-600 block">Eligible Lines:</span>
                <strong>{returnableData?.lines?.length || selectedSIV?.lines?.length || 0} line(s)</strong>
              </div>
            </div>
          </div>
        )}

        {/* Lines */}
        <div className="border-t border-slate-200 pt-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Returned Items</h3>
              <p className="text-xs text-slate-500">
                Return quantities are strictly validated against remaining returnable balances (Issued − Previously Returned).
              </p>
            </div>
            <button
              type="button"
              onClick={addLine}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add Custom Line</span>
            </button>
          </div>

          {lines.length === 0 ? (
            <div className="mt-4 rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
              {isLoadingReturnable ? (
                <div className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-rose-600" />
                  <span>Loading lines from referenced SIV...</span>
                </div>
              ) : referenceSivId ? (
                'No eligible returnable items found on this SIV (all issued quantities may have already been returned).'
              ) : (
                'Select an SIV voucher above to auto-populate returnable line items.'
              )}
            </div>
          ) : (
            <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                <thead className="bg-slate-50 font-semibold text-slate-700">
                  <tr>
                    <th className="py-2.5 px-3">Item SKU & Description</th>
                    <th className="py-2.5 px-3 text-center">Issued Qty (SIV)</th>
                    <th className="py-2.5 px-3 w-32">Return Qty *</th>
                    <th className="py-2.5 px-3 text-center">Unit</th>
                    <th className="py-2.5 px-3 text-right">Unit Price (ETB)</th>
                    <th className="py-2.5 px-3 text-right">Total Returned Value (ETB)</th>
                    <th className="py-2.5 px-3">Line Remarks</th>
                    <th className="py-2.5 px-2 text-center w-10"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {lines.map((line, idx) => {
                    const qtyNum = parseFloat(line.quantity) || 0
                    const priceNum = line.unit_price || 0
                    const lineTotal = qtyNum * priceNum
                    const isOver = line.remaining_returnable_quantity > 0 && qtyNum > line.remaining_returnable_quantity

                    return (
                      <tr key={idx} className={isOver ? 'bg-red-50/50' : 'hover:bg-slate-50/60'}>
                        <td className="py-2.5 px-3 min-w-[200px]">
                          {line.item_code ? (
                            <div className="space-y-0.5">
                              <span className="inline-block rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-bold text-slate-800">
                                {line.item_code}
                              </span>
                              <div className="text-[11px] text-slate-600 truncate max-w-xs">
                                {line.item_description || 'No description'}
                              </div>
                            </div>
                          ) : (
                            <ItemCombobox
                              value={line.item_id}
                              onChange={(newItemId, selectedItem) =>
                                handleItemChange(idx, newItemId, selectedItem)
                              }
                              required
                              placeholder="Select SKU..."
                              excludeItemIds={lines
                                .filter((_, i) => i !== idx)
                                .map((l) => l.item_id)
                                .filter(Boolean)}
                            />
                          )}
                        </td>

                        <td className="py-2.5 px-3 text-center">
                          {line.issued_quantity > 0 ? (
                            <span className="inline-flex items-center gap-1 rounded-md bg-rose-50 px-2 py-1 text-[11px] font-medium text-rose-800 border border-rose-200">
                              Issued: {line.issued_quantity}
                              <span className="text-slate-400">|</span>
                              <strong className="text-emerald-700">Avail: {line.remaining_returnable_quantity}</strong>
                            </span>
                          ) : (
                            <span className="text-slate-400 font-mono text-[11px]">N/A</span>
                          )}
                        </td>

                        <td className="py-2.5 px-3">
                          <input
                            type="number"
                            min="0.0001"
                            max={line.remaining_returnable_quantity > 0 ? line.remaining_returnable_quantity : undefined}
                            step="any"
                            value={line.quantity}
                            onChange={(e) => handleLineQtyChange(idx, e.target.value)}
                            required
                            className={`w-full rounded-lg border py-1.5 px-2 text-xs font-mono focus:outline-hidden ${
                              isOver
                                ? 'border-red-500 bg-red-50 text-red-900 focus:border-red-600'
                                : 'border-slate-300 bg-white focus:border-rose-500'
                            }`}
                          />
                          {isOver && (
                            <p className="mt-0.5 text-[10px] font-medium text-red-600">
                              Exceeds max returnable ({line.remaining_returnable_quantity} {line.unit})
                            </p>
                          )}
                        </td>

                        <td className="py-2.5 px-3 text-center">
                          <span className="inline-block rounded bg-slate-100 px-2 py-0.5 font-mono text-[11px] font-medium text-slate-700">
                            {line.unit}
                          </span>
                        </td>

                        <td className="py-2.5 px-3 text-right">
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={line.unit_price !== null ? line.unit_price : ''}
                            onChange={(e) => handleLinePriceChange(idx, e.target.value)}
                            placeholder="Inherited"
                            className="w-24 text-right rounded-lg border border-slate-300 py-1.5 px-2 text-xs font-mono bg-slate-50 focus:bg-white focus:border-rose-500 focus:outline-hidden"
                          />
                        </td>

                        <td className="py-2.5 px-3 text-right font-mono font-bold text-slate-800">
                          {lineTotal > 0
                            ? `ETB ${lineTotal.toLocaleString(undefined, {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}`
                            : '—'}
                        </td>

                        <td className="py-2.5 px-3 min-w-[130px]">
                          <input
                            type="text"
                            value={line.remarks}
                            onChange={(e) => handleLineRemarksChange(idx, e.target.value)}
                            placeholder="Surplus / condition"
                            className="w-full rounded-lg border border-slate-300 py-1.5 px-2 text-xs bg-white focus:border-rose-500 focus:outline-hidden"
                          />
                        </td>

                        <td className="py-2.5 px-2 text-center">
                          <button
                            type="button"
                            onClick={() => removeLine(idx)}
                            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-red-600 transition-colors"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Summary Box */}
          {lines.length > 0 && (
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center sm:text-left">
                <div>
                  <span className="block text-xs font-medium text-slate-500">Total Return Lines:</span>
                  <span className="font-mono text-base font-bold text-slate-800">
                    {totalReturnLines} item line(s)
                  </span>
                </div>
                <div>
                  <span className="block text-xs font-medium text-slate-500">Total Returned Quantity:</span>
                  <span className="font-mono text-base font-bold text-slate-800">
                    {totalReturnedQuantity.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 4,
                    })}
                  </span>
                </div>
                <div>
                  <span className="block text-xs font-medium text-slate-500">Total Returned Valuation (ETB):</span>
                  <span className="font-mono text-base font-bold text-emerald-700">
                    ETB {totalReturnedValuation.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between border-t border-slate-200 pt-5">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <ShieldAlert className="h-4 w-4 text-rose-600" />
            <span>Dual-write stock increment posted atomically with immutable movement (ADR-001)</span>
          </div>
          <button
            type="submit"
            disabled={isSubmitDisabled}
            className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-rose-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {createSRVMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Posting SRV Return Voucher...</span>
              </>
            ) : (
              <span>Post SRV Return Voucher</span>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}

export default SRVPage
