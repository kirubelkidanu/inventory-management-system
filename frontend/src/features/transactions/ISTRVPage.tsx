import React, { useState, useEffect, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { PackageOpen, Plus, Trash2, ShieldAlert, Loader2, AlertTriangle, ArrowLeft, Truck, Lock } from 'lucide-react'
import { useWarehouses } from '@/features/inventory/useInventoryData'
import { ItemCombobox } from '@/components/ItemCombobox'
import { cn } from '@/lib/utils'
import {
  useCreateISTRV,
  useInTransitTransfers,
  extractErrorMessage,
} from './useTransactionData'
import { VoucherSuccessCard } from './VoucherSuccessCard'
import type { Transaction, InTransitReportItem } from '@/types'

interface ISTRVLineForm {
  item_id: string
  item_code?: string
  item_description?: string
  quantity: string
  sent_quantity: number
  remaining_quantity: number
  unit: string
  unit_price: string
  remarks: string
}

export const ISTRVPage: React.FC = () => {
  const [searchParams] = useSearchParams()
  const initialIstvId = searchParams.get('istv_id') || ''

  const { data: warehouses = [], isLoading: isLoadingWarehouses } = useWarehouses()
  const { data: inTransitTransfers = [], isLoading: isLoadingTransfers } = useInTransitTransfers()

  const [selectedTransferId, setSelectedTransferId] = useState(initialIstvId)
  const [destinationWarehouseId, setDestinationWarehouseId] = useState('')
  const [transactionDate, setTransactionDate] = useState(
    new Date().toISOString().split('T')[0]
  )
  const [remarks, setRemarks] = useState('')
  const [lines, setLines] = useState<ISTRVLineForm[]>([
    {
      item_id: '',
      quantity: '1',
      sent_quantity: 1,
      remaining_quantity: 1,
      unit: 'PCS',
      unit_price: '0.00',
      remarks: '',
    },
  ])

  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [postedTransaction, setPostedTransaction] = useState<Transaction | null>(null)

  const createISTRVMutation = useCreateISTRV()

  // Group in-transit transfer lines by ISTV voucher
  const transferGroups = useMemo(() => {
    const map = new Map<string, InTransitReportItem[]>()
    for (const row of inTransitTransfers) {
      if (row.status !== 'COMPLETED' && Number(row.remaining_quantity) > 0) {
        const key = row.transfer_record_id || row.istv_transaction_id || row.istv_number
        if (!map.has(key)) {
          map.set(key, [])
        }
        map.get(key)!.push(row)
      }
    }
    return Array.from(map.entries()).map(([recordId, rows]) => ({
      recordId,
      firstRow: rows[0],
      rows,
    }))
  }, [inTransitTransfers])

  // When a transfer is selected from dropdown
  const handleSelectTransferGroup = (recordId: string) => {
    setSelectedTransferId(recordId)
    setErrorMessage(null)

    const match = transferGroups.find((g) => g.recordId === recordId)
    if (match) {
      setDestinationWarehouseId(match.firstRow.destination_warehouse_id || '')
      // Populate lines with remaining quantities and inherited unit price
      const newLines: ISTRVLineForm[] = match.rows.map((r) => {
        const remQty = Number(r.remaining_quantity) || 0
        const sentQty = Number(r.sent_quantity) || remQty
        const price =
          r.unit_price !== undefined && r.unit_price !== null
            ? Number(r.unit_price).toFixed(2)
            : '0.00'
        return {
          item_id: r.item_id,
          item_code: r.item_code,
          item_description: r.item_description,
          quantity: String(remQty),
          sent_quantity: sentQty,
          remaining_quantity: remQty,
          unit: r.unit || 'PCS',
          unit_price: price,
          remarks: `Received against ${r.istv_number}`,
        }
      })
      setLines(
        newLines.length > 0
          ? newLines
          : [
              {
                item_id: '',
                quantity: '1',
                sent_quantity: 1,
                remaining_quantity: 1,
                unit: 'PCS',
                unit_price: '0.00',
                remarks: '',
              },
            ]
      )
    } else {
      setDestinationWarehouseId('')
      setLines([
        {
          item_id: '',
          quantity: '1',
          sent_quantity: 1,
          remaining_quantity: 1,
          unit: 'PCS',
          unit_price: '0.00',
          remarks: '',
        },
      ])
    }
  }

  // Pre-select if initialIstvId provided
  useEffect(() => {
    if (initialIstvId && transferGroups.length > 0) {
      handleSelectTransferGroup(initialIstvId)
    }
  }, [initialIstvId, transferGroups])

  const addLine = () => {
    setLines([
      ...lines,
      {
        item_id: '',
        quantity: '1',
        sent_quantity: 1,
        remaining_quantity: 1,
        unit: 'PCS',
        unit_price: '0.00',
        remarks: '',
      },
    ])
  }

  const removeLine = (idx: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== idx))
    }
  }

  const totalQuantity = useMemo(() => {
    return lines.reduce((sum, line) => {
      const qty = parseFloat(line.quantity) || 0
      return sum + qty
    }, 0)
  }, [lines])

  const totalValuation = useMemo(() => {
    return lines.reduce((sum, line) => {
      const qty = parseFloat(line.quantity) || 0
      const price = parseFloat(line.unit_price) || 0
      return sum + qty * price
    }, 0)
  }, [lines])

  // Over-receiving condition check
  const hasOverReceiving = useMemo(() => {
    return lines.some((l) => {
      const q = parseFloat(l.quantity) || 0
      return q > l.remaining_quantity
    })
  }, [lines])

  const hasZeroTotal = totalQuantity <= 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!selectedTransferId) {
      setErrorMessage('Please select a pending in-transit transfer to receive.')
      return
    }

    if (!destinationWarehouseId) {
      setErrorMessage('Please confirm the receiving destination warehouse.')
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
      if (qty > line.remaining_quantity) {
        setErrorMessage(
          `Line ${i + 1}: Received quantity (${qty}) exceeds remaining in-transit quantity (${line.remaining_quantity}). Over-receiving is prohibited (ADR-005).`
        )
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
      setErrorMessage('Each item can only appear once in a voucher (ADR-006).')
      return
    }

    let targetIstvId = selectedTransferId
    const matchedGroup = transferGroups.find((g) => g.recordId === selectedTransferId)
    if (matchedGroup) {
      targetIstvId = matchedGroup.firstRow.istv_transaction_id || matchedGroup.firstRow.transfer_record_id
    }

    try {
      const payload = {
        istv_transaction_id: targetIstvId,
        destination_warehouse_id: destinationWarehouseId,
        transaction_date: transactionDate,
        remarks: remarks.trim() || null,
        lines: lines.map((l) => ({
          item_id: l.item_id,
          quantity: parseFloat(l.quantity),
          unit_price: l.unit_price !== '' && !isNaN(parseFloat(l.unit_price)) ? parseFloat(l.unit_price) : undefined,
          remarks: l.remarks.trim() || undefined,
        })),
      }

      const res = await createISTRVMutation.mutateAsync(payload)
      setPostedTransaction(res)
    } catch (err) {
      setErrorMessage(extractErrorMessage(err))
    }
  }

  const handleReset = () => {
    setPostedTransaction(null)
    setSelectedTransferId('')
    setDestinationWarehouseId('')
    setRemarks('')
    setLines([
      {
        item_id: '',
        quantity: '1',
        sent_quantity: 1,
        remaining_quantity: 1,
        unit: 'PCS',
        unit_price: '0.00',
        remarks: '',
      },
    ])
    setErrorMessage(null)
  }

  if (postedTransaction) {
    return (
      <div className="mx-auto max-w-4xl py-6">
        <VoucherSuccessCard
          transaction={postedTransaction}
          title="Inter-Store Transfer Receiving Voucher (ISTRV)"
          onReset={handleReset}
        />
      </div>
    )
  }

  const selectedGroup = transferGroups.find((g) => g.recordId === selectedTransferId)

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-teal-100 p-2.5 text-teal-700 shadow-xs">
            <PackageOpen className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Inter-Store Transfer Receiving Voucher (ISTRV)
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Acknowledge and receive in-transit shipments at destination store. Automatically closes transit state, inherits originating transfer valuation, and credits destination warehouse stock.
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
          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-700">Select In-Transit Dispatch *</label>
            <select
              value={selectedTransferId}
              onChange={(e) => handleSelectTransferGroup(e.target.value)}
              required
              disabled={isLoadingTransfers}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-teal-500 focus:outline-hidden"
            >
              <option value="">
                {isLoadingTransfers
                  ? 'Loading in-transit dispatches...'
                  : transferGroups.length === 0
                  ? 'No pending in-transit transfers found'
                  : 'Select an in-transit dispatch to receive...'}
              </option>
              {transferGroups.map((group) => {
                const f = group.firstRow
                return (
                  <option key={group.recordId} value={group.recordId}>
                    {f.istv_number} — {f.source_warehouse_name} &rarr; {f.destination_warehouse_name} ({f.plate_no || 'No Plate'} / {f.driver_name || 'Driver'}) — {group.rows.length} item(s)
                  </option>
                )
              })}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Receipt Date *</label>
            <input
              type="date"
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
              required
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-teal-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Destination Warehouse *</label>
            <select
              value={destinationWarehouseId}
              onChange={(e) => setDestinationWarehouseId(e.target.value)}
              required
              disabled={isLoadingWarehouses || Boolean(selectedGroup)}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-teal-500 focus:outline-hidden disabled:bg-slate-100 disabled:text-slate-600 disabled:cursor-not-allowed"
            >
              <option value="">Select Destination Warehouse...</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
            {selectedGroup && (
              <p className="mt-1 text-[11px] font-medium text-teal-700 flex items-center gap-1">
                <Lock className="h-3 w-3 inline text-teal-600" />
                <span>Locked to destination store from dispatch record</span>
              </p>
            )}
          </div>

          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-700">Receiving Remarks / Notes</label>
            <input
              type="text"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="Goods condition, container seal intact, bay location, etc."
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-teal-500 focus:outline-hidden"
            />
          </div>
        </div>

        {/* Selected transfer card */}
        {selectedGroup && (
          <div className="rounded-xl border border-teal-200 bg-teal-50/50 p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-teal-900 mb-2">
              <Truck className="h-4 w-4 text-teal-600" />
              <span>In-Transit Logistics Information</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs text-teal-800 sm:grid-cols-4">
              <div>
                <span className="text-teal-600 block">Source Store:</span>
                <strong>{selectedGroup.firstRow.source_warehouse_name}</strong>
              </div>
              <div>
                <span className="text-teal-600 block">Destination:</span>
                <strong>{selectedGroup.firstRow.destination_warehouse_name}</strong>
              </div>
              <div>
                <span className="text-teal-600 block">Vehicle Plate:</span>
                <strong>{selectedGroup.firstRow.plate_no || 'N/A'}</strong>
              </div>
              <div>
                <span className="text-teal-600 block">Driver:</span>
                <strong>{selectedGroup.firstRow.driver_name || 'N/A'}</strong>
              </div>
            </div>
          </div>
        )}

        {/* Lines */}
        <div className="border-t border-slate-200 pt-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Items to Receive</h3>
              <p className="text-xs text-slate-500">
                Partial receiving is fully supported. Over-receiving exceeding in-transit stock is strictly prohibited (ADR-005).
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
              const qtyNum = parseFloat(line.quantity) || 0
              const priceNum = parseFloat(line.unit_price) || 0
              const lineTotal = qtyNum * priceNum
              const isOver = qtyNum > line.remaining_quantity

              return (
                <div
                  key={idx}
                  className={cn(
                    "flex flex-wrap lg:flex-nowrap items-start gap-3 rounded-xl border p-3.5 transition-colors",
                    isOver
                      ? "border-red-300 bg-red-50/50"
                      : "border-slate-200 bg-slate-50/60"
                  )}
                >
                  <div className="flex-1 min-w-[220px]">
                    <label className="block text-[11px] font-medium text-slate-500 mb-1">
                      Item SKU & Description *
                    </label>
                    {line.item_code ? (
                      <div className="flex flex-col justify-center rounded-lg border border-slate-200 bg-white py-1.5 px-3 min-h-[34px]">
                        <div className="flex items-center gap-2">
                          <span className="inline-block rounded-md bg-teal-100 px-1.5 py-0.5 font-mono text-[11px] font-bold text-teal-800">
                            {line.item_code}
                          </span>
                          <span className="truncate text-xs font-medium text-slate-800">
                            {line.item_description}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <ItemCombobox
                        value={line.item_id}
                        onChange={(newItemId, item) => {
                          const updated = [...lines]
                          updated[idx].item_id = newItemId
                          if (item) {
                            updated[idx].item_code = item.item_code
                            updated[idx].item_description = item.description
                            if (item.default_unit) updated[idx].unit = item.default_unit
                            if (item.latest_unit_price !== undefined && item.latest_unit_price !== null) {
                              updated[idx].unit_price = Number(item.latest_unit_price).toFixed(2)
                            }
                          }
                          setLines(updated)
                        }}
                        required
                        placeholder="Search SKU or description..."
                        excludeItemIds={lines.filter((_, i) => i !== idx).map((l) => l.item_id).filter(Boolean)}
                      />
                    )}
                  </div>

                  <div className="w-36">
                    <label className="block text-[11px] font-medium text-slate-500 mb-1">In-Transit Qty</label>
                    <div className="flex items-center h-[34px] rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-900">
                      <span>Rem: {line.remaining_quantity} / Sent: {line.sent_quantity}</span>
                    </div>
                  </div>

                  <div className="w-28">
                    <label className="block text-[11px] font-medium text-slate-500 mb-1">Receive Qty *</label>
                    <input
                      type="number"
                      min="0.0001"
                      max={line.remaining_quantity}
                      step="0.0001"
                      value={line.quantity}
                      onChange={(e) => {
                        const updated = [...lines]
                        updated[idx].quantity = e.target.value
                        setLines(updated)
                      }}
                      required
                      className={cn(
                        "block w-full rounded-lg border py-2 px-3 text-xs bg-white font-mono focus:outline-hidden",
                        isOver
                          ? "border-red-500 text-red-700 bg-red-50 focus:border-red-600"
                          : "border-slate-300 focus:border-teal-500"
                      )}
                    />
                    {isOver && (
                      <p className="mt-1 text-[10px] font-semibold text-red-600 leading-tight">
                        Cannot exceed remaining in-transit quantity ({line.remaining_quantity})
                      </p>
                    )}
                  </div>

                  <div className="w-20">
                    <label className="block text-[11px] font-medium text-slate-500 mb-1">Unit</label>
                    <div className="flex items-center h-[34px] rounded-lg border border-slate-200 bg-slate-100/70 py-2 px-3 text-xs font-mono font-medium text-slate-700">
                      {line.unit || 'PCS'}
                    </div>
                  </div>

                  <div className="w-28">
                    <label className="block text-[11px] font-medium text-slate-500 mb-1">Unit Price (ETB)</label>
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
                      className="block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-teal-500 focus:outline-hidden"
                    />
                  </div>

                  <div className="w-32">
                    <label className="block text-[11px] font-medium text-slate-500 mb-1">Total Value (ETB)</label>
                    <div className="flex items-center h-[34px] rounded-lg border border-slate-200 bg-slate-100/70 py-2 px-3 text-xs font-mono font-semibold text-slate-800">
                      {lineTotal.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </div>
                  </div>

                  <div className="flex-1 min-w-[150px]">
                    <label className="block text-[11px] font-medium text-slate-500 mb-1">Line Remarks</label>
                    <input
                      type="text"
                      value={line.remarks}
                      onChange={(e) => {
                        const updated = [...lines]
                        updated[idx].remarks = e.target.value
                        setLines(updated)
                      }}
                      placeholder="Condition / Bay"
                      className="block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white focus:border-teal-500 focus:outline-hidden"
                    />
                  </div>

                  <div className="pt-6">
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
                <span className="text-xs font-medium text-slate-500">Total Items</span>
                <p className="font-mono text-sm font-bold text-slate-800">{lines.length}</p>
              </div>
              <div className="border-l border-slate-200 pl-6">
                <span className="text-xs font-medium text-slate-500">Total Received Quantity</span>
                <p className="font-mono text-sm font-bold text-slate-800">
                  {totalQuantity.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 4 })}
                </p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs font-medium text-slate-500">Total Received Valuation (ETB)</span>
              <p className="font-mono text-lg font-extrabold text-teal-700">
                ETB {totalValuation.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between border-t border-slate-200 pt-5">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <ShieldAlert className="h-4 w-4 text-teal-600" />
            <span>Updates transit records and credits destination warehouse stock with inherited valuation (ADR-005)</span>
          </div>
          <button
            type="submit"
            disabled={
              createISTRVMutation.isPending ||
              hasOverReceiving ||
              hasZeroTotal ||
              !selectedTransferId ||
              !destinationWarehouseId
            }
            className="inline-flex items-center gap-2 rounded-xl bg-teal-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-teal-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {createISTRVMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Receiving Transfer...</span>
              </>
            ) : (
              <span>Confirm & Post ISTRV Receipt</span>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}

export default ISTRVPage
