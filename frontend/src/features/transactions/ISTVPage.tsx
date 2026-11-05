import React, { useState, useEffect, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Truck, Plus, Trash2, ShieldAlert, Loader2, AlertTriangle, ArrowLeft } from 'lucide-react'
import { useWarehouses } from '@/features/inventory/useInventoryData'
import { ItemCombobox } from '@/components/ItemCombobox'
import api from '@/lib/api'
import {
  useProjects,
  useCreateISTV,
  extractErrorMessage,
} from './useTransactionData'
import { VoucherSuccessCard } from './VoucherSuccessCard'
import type { Item, Transaction } from '@/types'

interface ISTVLineForm {
  item_id: string
  quantity: string
  unit: string
  unit_price: string
  remarks: string
}

export const ISTVPage: React.FC = () => {
  const [searchParams] = useSearchParams()
  const initialSourceWhId = searchParams.get('source_warehouse_id') || searchParams.get('warehouse_id') || ''
  const initialItemId = searchParams.get('item_id') || ''

  const { data: warehouses = [], isLoading: isLoadingWarehouses } = useWarehouses()
  const { data: projects = [], isLoading: isLoadingProjects } = useProjects()

  const [sourceWarehouseId, setSourceWarehouseId] = useState(initialSourceWhId)
  const [destWarehouseId, setDestWarehouseId] = useState('')
  const [projectId, setProjectId] = useState('')
  const [istvNo, setIstvNo] = useState('')
  const [plateNo, setPlateNo] = useState('')
  const [driverName, setDriverName] = useState('')
  const [materialSummary, setMaterialSummary] = useState('')
  const [transactionDate, setTransactionDate] = useState(
    new Date().toISOString().split('T')[0]
  )
  const [remarks, setRemarks] = useState('')
  const [lines, setLines] = useState<ISTVLineForm[]>([
    { item_id: initialItemId, quantity: '1', unit: 'PCS', unit_price: '0.00', remarks: '' },
  ])
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [postedTransaction, setPostedTransaction] = useState<Transaction | null>(null)

  const createISTVMutation = useCreateISTV()

  // Update initial line unit and price if initialItemId is provided
  useEffect(() => {
    if (initialItemId) {
      api.get<Item>(`/items/${initialItemId}`).then((res) => {
        if (res.data) {
          setLines((prev) => {
            const updated = [...prev]
            if (updated[0] && updated[0].item_id === initialItemId) {
              if (res.data.default_unit) updated[0].unit = res.data.default_unit
              if (res.data.latest_unit_price !== undefined && res.data.latest_unit_price !== null && Number(res.data.latest_unit_price) >= 0) {
                updated[0].unit_price = Number(res.data.latest_unit_price).toFixed(2)
              }
            }
            return updated
          })
        }
      }).catch(() => {})
    }
  }, [initialItemId])

  // Update source warehouse if query parameter arrives after mount
  useEffect(() => {
    if (initialSourceWhId && !sourceWarehouseId) {
      setSourceWarehouseId(initialSourceWhId)
    }
  }, [initialSourceWhId, sourceWarehouseId])

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
          { params: sourceWarehouseId ? { warehouse_id: sourceWarehouseId } : {} }
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
    setLines([...lines, { item_id: '', quantity: '1', unit: 'PCS', unit_price: '0.00', remarks: '' }])
  }

  const removeLine = (idx: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== idx))
    }
  }

  const totalValuation = useMemo(() => {
    return lines.reduce((sum, line) => {
      const qty = parseFloat(line.quantity) || 0
      const price = parseFloat(line.unit_price) || 0
      return sum + qty * price
    }, 0)
  }, [lines])

  const totalQuantity = useMemo(() => {
    return lines.reduce((sum, line) => {
      const qty = parseFloat(line.quantity) || 0
      return sum + qty
    }, 0)
  }, [lines])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!sourceWarehouseId) {
      setErrorMessage('Please select a source warehouse (FROM).')
      return
    }

    if (!destWarehouseId) {
      setErrorMessage('Please select a destination warehouse (TO).')
      return
    }

    if (sourceWarehouseId === destWarehouseId) {
      setErrorMessage('Source warehouse and destination warehouse must be different.')
      return
    }

    // Validate lines
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      if (!line.item_id) {
        setErrorMessage(`Line ${i + 1}: Item SKU is required.`)
        return
      }
      const qty = parseFloat(line.quantity)
      if (isNaN(qty) || qty <= 0) {
        setErrorMessage(`Line ${i + 1}: Quantity must be greater than zero.`)
        return
      }
      if (!line.unit.trim()) {
        setErrorMessage(`Line ${i + 1}: Unit of measurement is required.`)
        return
      }
      const price = line.unit_price !== '' ? parseFloat(line.unit_price) : 0
      if (isNaN(price) || price < 0) {
        setErrorMessage(`Line ${i + 1}: Unit price must be greater than or equal to 0.`)
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
        source_warehouse_id: sourceWarehouseId,
        destination_warehouse_id: destWarehouseId,
        project_id: projectId || null,
        transaction_date: transactionDate,
        istv_no: istvNo.trim() || null,
        plate_no: plateNo.trim() || null,
        driver_name: driverName.trim() || null,
        material_summary: materialSummary.trim() || null,
        remarks: remarks.trim() || null,
        lines: lines.map((l) => ({
          item_id: l.item_id,
          quantity: parseFloat(l.quantity),
          unit: l.unit.trim(),
          unit_price: l.unit_price !== '' && !isNaN(parseFloat(l.unit_price)) ? parseFloat(l.unit_price) : 0,
          remarks: l.remarks.trim() || undefined,
        })),
      }

      const res = await createISTVMutation.mutateAsync(payload)
      setPostedTransaction(res)
    } catch (err) {
      setErrorMessage(extractErrorMessage(err))
    }
  }

  const handleReset = () => {
    setPostedTransaction(null)
    setIstvNo('')
    setPlateNo('')
    setDriverName('')
    setMaterialSummary('')
    setRemarks('')
    setLines([{ item_id: '', quantity: '1', unit: 'PCS', unit_price: '0.00', remarks: '' }])
    setErrorMessage(null)
  }

  if (postedTransaction) {
    return (
      <div className="mx-auto max-w-4xl py-6">
        <VoucherSuccessCard
          transaction={postedTransaction}
          title="Inter-Store Transfer Voucher (ISTV)"
          onReset={handleReset}
        />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-purple-100 p-2.5 text-purple-700 shadow-xs">
            <Truck className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Inter-Store Transfer Voucher (ISTV)
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Dispatch inventory between company warehouses. Decrements source stock, logs transport vehicle/driver accountability, and creates tracked in-transit records with accurate unit valuation.
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700">Source Warehouse (FROM) *</label>
            <select
              value={sourceWarehouseId}
              onChange={(e) => setSourceWarehouseId(e.target.value)}
              required
              disabled={isLoadingWarehouses}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-purple-500 focus:outline-hidden"
            >
              <option value="">{isLoadingWarehouses ? 'Loading warehouses...' : 'Select Origin...'}</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id} disabled={w.id === destWarehouseId}>
                  {w.code} — {w.name} {w.id === destWarehouseId ? '(Destination)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Destination Warehouse (TO) *</label>
            <select
              value={destWarehouseId}
              onChange={(e) => setDestWarehouseId(e.target.value)}
              required
              disabled={isLoadingWarehouses}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-purple-500 focus:outline-hidden"
            >
              <option value="">{isLoadingWarehouses ? 'Loading warehouses...' : 'Select Destination...'}</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id} disabled={w.id === sourceWarehouseId}>
                  {w.code} — {w.name} {w.id === sourceWarehouseId ? '(Source)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Dispatch Date *</label>
            <input
              type="date"
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
              required
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-purple-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">ISTV Voucher Ref #</label>
            <input
              type="text"
              value={istvNo}
              onChange={(e) => setIstvNo(e.target.value)}
              placeholder="e.g. ISTV-2026-0045"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-purple-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Vehicle Plate No</label>
            <input
              type="text"
              value={plateNo}
              onChange={(e) => setPlateNo(e.target.value)}
              placeholder="e.g. AA-3-A12345"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-purple-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Driver Name</label>
            <input
              type="text"
              value={driverName}
              onChange={(e) => setDriverName(e.target.value)}
              placeholder="e.g. Abebe Kebede"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-purple-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Associated Project</label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              disabled={isLoadingProjects}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-purple-500 focus:outline-hidden"
            >
              <option value="">{isLoadingProjects ? 'Loading projects...' : 'General Transfer / Unallocated'}</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} — {p.name}
                </option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-700">Material Summary</label>
            <input
              type="text"
              value={materialSummary}
              onChange={(e) => setMaterialSummary(e.target.value)}
              placeholder="e.g. Structural steel and plumbing supplies for regional branch"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-purple-500 focus:outline-hidden"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700">Remarks / Transfer Instructions</label>
          <input
            type="text"
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
            placeholder="Handling precautions, delivery notes, or route info..."
            className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-purple-500 focus:outline-hidden"
          />
        </div>

        {/* Lines */}
        <div className="border-t border-slate-200 pt-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Dispatched Items</h3>
              <p className="text-xs text-slate-500">Source warehouse must hold sufficient available stock. Unit price defaults to latest inbound acquisition cost.</p>
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
                  <div className="flex-1 min-w-[220px]">
                    <label className="block text-[11px] font-medium text-slate-500 mb-1">Item SKU & Description *</label>
                    <ItemCombobox
                      value={line.item_id}
                      onChange={(newItemId, selectedItem) => handleItemChange(idx, newItemId, selectedItem)}
                      required
                      placeholder="Search SKU or description..."
                      excludeItemIds={lines.filter((_, i) => i !== idx).map((l) => l.item_id).filter(Boolean)}
                    />
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
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-purple-500 focus:outline-hidden"
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
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-purple-500 focus:outline-hidden"
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
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-purple-500 focus:outline-hidden"
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

                  <div className="flex-1 min-w-[150px]">
                    <label className="block text-[11px] font-medium text-slate-500">Line Remarks</label>
                    <input
                      type="text"
                      value={line.remarks}
                      onChange={(e) => {
                        const updated = [...lines]
                        updated[idx].remarks = e.target.value
                        setLines(updated)
                      }}
                      placeholder="e.g. Bundle 4"
                      className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white focus:border-purple-500 focus:outline-hidden"
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

          {/* Summary Box */}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="flex items-center gap-6">
              <div>
                <span className="text-xs font-medium text-slate-500">Total Lines</span>
                <p className="font-mono text-sm font-bold text-slate-800">{lines.length}</p>
              </div>
              <div className="border-l border-slate-200 pl-6">
                <span className="text-xs font-medium text-slate-500">Total Dispatched Quantity</span>
                <p className="font-mono text-sm font-bold text-slate-800">
                  {totalQuantity.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 4 })}
                </p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs font-medium text-slate-500">Total Dispatched Valuation (ETB)</span>
              <p className="font-mono text-lg font-extrabold text-purple-700">
                ETB {totalValuation.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between border-t border-slate-200 pt-5">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <ShieldAlert className="h-4 w-4 text-emerald-600" />
            <span>Decrements source stock and initiates in-transit transfer tracking (ADR-004, ADR-005)</span>
          </div>
          <button
            type="submit"
            disabled={createISTVMutation.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-purple-500 disabled:opacity-50 transition-colors"
          >
            {createISTVMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Dispatching Transfer...</span>
              </>
            ) : (
              <span>Post ISTV Transfer Dispatch</span>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}

export default ISTVPage
