import React, { useState, useEffect, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Sliders, Plus, Trash2, ShieldAlert, Loader2, AlertTriangle, ArrowLeft, Lock } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useWarehouses } from '@/features/inventory/useInventoryData'
import { ItemCombobox } from '@/components/ItemCombobox'
import api from '@/lib/api'
import {
  useProjects,
  useCreateAdjustment,
  extractErrorMessage,
} from './useTransactionData'
import { VoucherSuccessCard } from './VoucherSuccessCard'
import type { Item, Transaction } from '@/types'

export const AdjustmentPage: React.FC = () => {
  const { user } = useAuth()
  const isAuthorized = user?.role === 'ADMIN' || user?.role === 'INVENTORY_MANAGER'

  const [searchParams] = useSearchParams()
  const initialWarehouseId = searchParams.get('warehouse_id') || ''
  const initialItemId = searchParams.get('item_id') || ''

  const { data: warehouses = [], isLoading: isLoadingWarehouses } = useWarehouses()
  const { data: projects = [], isLoading: isLoadingProjects } = useProjects()

  const [warehouseId, setWarehouseId] = useState(initialWarehouseId)
  const [projectId, setProjectId] = useState('')
  const [transactionDate, setTransactionDate] = useState(
    new Date().toISOString().split('T')[0]
  )
  const [adjustmentReason, setAdjustmentReason] = useState('')
  const [remarks, setRemarks] = useState('')
  const [lines, setLines] = useState<Array<{
    item_id: string
    direction: 'IN' | 'OUT'
    quantity: string
    unit: string
    unit_price: string
    remarks: string
  }>>([
    { item_id: initialItemId, direction: 'IN', quantity: '1', unit: 'PCS', unit_price: '0.00', remarks: '' },
  ])

  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [postedTransaction, setPostedTransaction] = useState<Transaction | null>(null)

  const createAdjustmentMutation = useCreateAdjustment()

  // Update initial line unit and cost if initialItemId is provided
  useEffect(() => {
    if (initialItemId) {
      api.get<Item>(`/items/${initialItemId}`).then((res) => {
        if (res.data?.default_unit) {
          setLines((prev) => {
            const updated = [...prev]
            if (updated[0] && updated[0].item_id === initialItemId) {
              updated[0].unit = res.data.default_unit
              if (res.data.latest_unit_price !== undefined && res.data.latest_unit_price !== null && Number(res.data.latest_unit_price) >= 0) {
                updated[0].unit_price = Number(res.data.latest_unit_price).toFixed(2)
              }
            }
            return updated
          })
        }
      }).catch(() => {})

      api.get<{ item_id: string; latest_unit_price: number | null }>(
        `/items/${initialItemId}/latest-cost`,
        { params: warehouseId ? { warehouse_id: warehouseId } : {} }
      ).then((costRes) => {
        if (costRes.data?.latest_unit_price !== undefined && costRes.data?.latest_unit_price !== null) {
          setLines((prev) => {
            const updated = [...prev]
            if (updated[0] && updated[0].item_id === initialItemId) {
              updated[0].unit_price = Number(costRes.data.latest_unit_price).toFixed(2)
            }
            return updated
          })
        }
      }).catch(() => {})
    }
  }, [initialItemId, warehouseId])

  // Update warehouse if query parameter arrives after mount
  useEffect(() => {
    if (initialWarehouseId && !warehouseId) {
      setWarehouseId(initialWarehouseId)
    }
  }, [initialWarehouseId, warehouseId])

  const handleItemChange = async (idx: number, newItemId: string, item?: Item) => {
    const updated = [...lines]
    updated[idx].item_id = newItemId
    if (item?.default_unit) {
      updated[idx].unit = item.default_unit
    }

    // Auto-populate unit price if available on item object
    if (item?.latest_unit_price !== undefined && item?.latest_unit_price !== null && Number(item.latest_unit_price) >= 0) {
      updated[idx].unit_price = Number(item.latest_unit_price).toFixed(2)
    } else {
      updated[idx].unit_price = '0.00'
    }
    setLines(updated)

    // Also query latest-cost endpoint for warehouse-specific cost if available
    if (newItemId) {
      try {
        const costRes = await api.get<{ item_id: string; latest_unit_price: number | null }>(
          `/items/${newItemId}/latest-cost`,
          { params: warehouseId ? { warehouse_id: warehouseId } : {} }
        )
        if (costRes.data?.latest_unit_price !== undefined && costRes.data?.latest_unit_price !== null) {
          setLines((prev) => {
            const current = [...prev]
            if (current[idx] && current[idx].item_id === newItemId) {
              current[idx].unit_price = Number(costRes.data.latest_unit_price).toFixed(2)
            }
            return current
          })
        }
      } catch {
        // Keep initial price if lookup fails
      }
    }
  }

  const addLine = () => {
    setLines([
      ...lines,
      { item_id: '', direction: 'IN', quantity: '1', unit: 'PCS', unit_price: '0.00', remarks: '' },
    ])
  }

  const removeLine = (idx: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== idx))
    }
  }

  // Live Totals
  const totalLines = lines.length

  const netAdjustedQuantity = useMemo(() => {
    return lines.reduce((sum, line) => {
      const qty = parseFloat(line.quantity) || 0
      return sum + (line.direction === 'OUT' ? -qty : qty)
    }, 0)
  }, [lines])

  const totalGrossValuation = useMemo(() => {
    return lines.reduce((sum, line) => {
      const qty = parseFloat(line.quantity) || 0
      const price = parseFloat(line.unit_price) || 0
      return sum + qty * price
    }, 0)
  }, [lines])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!isAuthorized) {
      setErrorMessage('Access Denied: Stock adjustments require Admin or Inventory Manager privileges.')
      return
    }

    if (!warehouseId) {
      setErrorMessage('Please select a warehouse.')
      return
    }

    if (!adjustmentReason.trim()) {
      setErrorMessage('Mandatory adjustment reason cannot be empty or whitespace.')
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
        adjustment_reason: adjustmentReason.trim(),
        remarks: remarks.trim() || null,
        lines: lines.map((l) => {
          const priceVal = parseFloat(l.unit_price)
          return {
            item_id: l.item_id,
            direction: l.direction,
            quantity: parseFloat(l.quantity),
            unit: l.unit.trim(),
            unit_price: !isNaN(priceVal) && priceVal >= 0 ? priceVal : null,
            remarks: l.remarks.trim() || undefined,
          }
        }),
      }

      const res = await createAdjustmentMutation.mutateAsync(payload)
      setPostedTransaction(res)
    } catch (err) {
      setErrorMessage(extractErrorMessage(err))
    }
  }

  const handleReset = () => {
    setPostedTransaction(null)
    setAdjustmentReason('')
    setRemarks('')
    setLines([
      { item_id: '', direction: 'IN', quantity: '1', unit: 'PCS', unit_price: '0.00', remarks: '' },
    ])
    setErrorMessage(null)
  }

  if (postedTransaction) {
    return (
      <div className="mx-auto max-w-4xl py-6">
        <VoucherSuccessCard
          transaction={postedTransaction}
          title="Stock Adjustment Voucher"
          onReset={handleReset}
        />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-amber-100 p-2.5 text-amber-700 shadow-xs">
            <Sliders className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Stock Adjustment Voucher
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Apply audited manual inventory adjustments (surplus count, write-off, damage, or shrinkage). Restricted to privileged roles.
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

      {!isAuthorized && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <Lock className="h-5 w-5 shrink-0 text-amber-600 mt-0.5" />
          <div>
            <span className="font-semibold">Privileged Access Required:</span> Stock adjustments are restricted to <strong>ADMIN</strong> and <strong>INVENTORY_MANAGER</strong> roles. Your current role is <strong>{user?.role || 'VIEWER'}</strong>. Submission is disabled.
          </div>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 animate-in fade-in">
          <AlertTriangle className="h-5 w-5 shrink-0 text-red-600 mt-0.5" />
          <div>
            <span className="font-semibold">Transaction Rejected:</span> {errorMessage}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700">Target Warehouse *</label>
            <select
              value={warehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
              required
              disabled={isLoadingWarehouses}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-amber-500 focus:outline-hidden"
            >
              <option value="">Select Warehouse...</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Associated Project</label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              disabled={isLoadingProjects}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-amber-500 focus:outline-hidden"
            >
              <option value="">General Stock / Unassigned</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} — {p.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Adjustment Date *</label>
            <input
              type="date"
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
              required
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-amber-500 focus:outline-hidden"
            />
          </div>

          <div className="sm:col-span-2 lg:col-span-3">
            <label className="block text-xs font-semibold text-slate-700">
              Mandatory Adjustment Reason * <span className="font-normal text-slate-400">(Required for audit log)</span>
            </label>
            <textarea
              rows={2}
              value={adjustmentReason}
              onChange={(e) => setAdjustmentReason(e.target.value)}
              required
              minLength={3}
              placeholder="State precise reason: e.g. Physical inventory count reconciliation / Damaged during shelf collapse / Scrap write-off approved by Management"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-amber-500 focus:outline-hidden"
            />
          </div>

          <div className="sm:col-span-2 lg:col-span-3">
            <label className="block text-xs font-semibold text-slate-700">Additional Remarks / Documentation Ref</label>
            <input
              type="text"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="Inspection certificate #, incident report ref, or committee authorization ID"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-amber-500 focus:outline-hidden"
            />
          </div>
        </div>

        {/* Lines */}
        <div className="border-t border-slate-200 pt-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Adjustment Items</h3>
              <p className="text-xs text-slate-500">
                Direction determines whether stock is added (IN) or deducted (OUT). Deductions require sufficient stock.
              </p>
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
              const qty = parseFloat(line.quantity) || 0
              const price = parseFloat(line.unit_price) || 0
              const lineTotal = qty * price

              return (
                <div key={idx} className="flex flex-wrap sm:flex-nowrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/60 p-3.5">
                  <div className="w-28 shrink-0">
                    <label className="block text-[11px] font-medium text-slate-500">Direction *</label>
                    <select
                      value={line.direction}
                      onChange={(e) => {
                        const updated = [...lines]
                        updated[idx].direction = e.target.value as 'IN' | 'OUT'
                        setLines(updated)
                      }}
                      required
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-2 text-xs font-semibold bg-white focus:border-amber-500 focus:outline-hidden"
                    >
                      <option value="IN">+ IN</option>
                      <option value="OUT">- OUT</option>
                    </select>
                  </div>

                  <div className="flex-1 min-w-[200px]">
                    <label className="block text-[11px] font-medium text-slate-500 mb-1">Item SKU & Description *</label>
                    <ItemCombobox
                      value={line.item_id}
                      onChange={(newItemId, selectedItem) => handleItemChange(idx, newItemId, selectedItem)}
                      required
                      placeholder="Search SKU or description..."
                      excludeItemIds={lines.filter((_, i) => i !== idx).map((l) => l.item_id).filter(Boolean)}
                    />
                  </div>

                  <div className="w-24 shrink-0">
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
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-amber-500 focus:outline-hidden"
                    />
                  </div>

                  <div className="w-20 shrink-0">
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
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-amber-500 focus:outline-hidden"
                    />
                  </div>

                  <div className="w-28 shrink-0">
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
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-amber-500 focus:outline-hidden"
                    />
                  </div>

                  <div className="w-32 shrink-0">
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
                      placeholder="Condition note"
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white focus:border-amber-500 focus:outline-hidden"
                    />
                  </div>

                  <div className="pt-4 shrink-0">
                    <button
                      type="button"
                      onClick={() => removeLine(idx)}
                      disabled={lines.length === 1}
                      className="rounded-lg p-2 text-slate-400 hover:bg-slate-200 hover:text-red-600 disabled:opacity-30 transition-colors"
                      title="Remove line"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Adjustment Summary Footer */}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-amber-100 bg-amber-50/60 p-4">
            <div className="flex items-center gap-6">
              <div>
                <span className="text-xs font-medium text-slate-500">Total Adjustment Lines</span>
                <p className="font-mono text-sm font-bold text-slate-800">{totalLines}</p>
              </div>
              <div className="border-l border-amber-200 pl-6">
                <span className="text-xs font-medium text-slate-500">Net Adjusted Quantity</span>
                <p className={`font-mono text-sm font-bold ${netAdjustedQuantity > 0 ? 'text-emerald-700' : netAdjustedQuantity < 0 ? 'text-amber-700' : 'text-slate-800'}`}>
                  {netAdjustedQuantity > 0 ? `+${netAdjustedQuantity.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 4 })}` : netAdjustedQuantity.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 4 })}
                </p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs font-medium text-slate-500">Total Gross Adjusted Valuation (ETB)</span>
              <p className="font-mono text-lg font-extrabold text-amber-700">
                ETB {totalGrossValuation.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between border-t border-slate-200 pt-5">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <ShieldAlert className="h-4 w-4 text-amber-600" />
            <span>Dual-write ledger entry with before/after state logged in audit_logs (ADR-001)</span>
          </div>
          <button
            type="submit"
            disabled={createAdjustmentMutation.isPending || !isAuthorized}
            className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-amber-500 disabled:opacity-50 transition-colors"
          >
            {createAdjustmentMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Applying Adjustment...</span>
              </>
            ) : (
              <span>Post Stock Adjustment</span>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}

export default AdjustmentPage
