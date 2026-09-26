import React, { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { PackageOpen, Plus, Trash2, ShieldAlert, Loader2, AlertTriangle, ArrowLeft, Truck } from 'lucide-react'
import { useWarehouses, useItems } from '@/features/inventory/useInventoryData'
import {
  useCreateISTRV,
  useInTransitTransfers,
  extractErrorMessage,
} from './useTransactionData'
import { VoucherSuccessCard } from './VoucherSuccessCard'
import type { Transaction, InTransitReportItem } from '@/types'

export const ISTRVPage: React.FC = () => {
  const [searchParams] = useSearchParams()
  const initialIstvId = searchParams.get('istv_id') || ''

  const { data: warehouses = [], isLoading: isLoadingWarehouses } = useWarehouses()
  const { data: itemsData, isLoading: isLoadingItems } = useItems({ limit: 1000 })
  const items = itemsData?.items || []
  const { data: inTransitTransfers = [], isLoading: isLoadingTransfers } = useInTransitTransfers()

  const [selectedTransferId, setSelectedTransferId] = useState(initialIstvId)
  const [destinationWarehouseId, setDestinationWarehouseId] = useState('')
  const [transactionDate, setTransactionDate] = useState(
    new Date().toISOString().split('T')[0]
  )
  const [remarks, setRemarks] = useState('')
  const [lines, setLines] = useState<Array<{
    item_id: string
    quantity: string
    maxRemaining?: number
    remarks: string
  }>>([{ item_id: '', quantity: '1', remarks: '' }])

  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [postedTransaction, setPostedTransaction] = useState<Transaction | null>(null)

  const createISTRVMutation = useCreateISTRV()

  // Group in-transit transfer lines by ISTV voucher
  const transferGroups = React.useMemo(() => {
    const map = new Map<string, InTransitReportItem[]>()
    for (const row of inTransitTransfers) {
      if (row.status !== 'COMPLETED' && Number(row.remaining_quantity) > 0) {
        // Group by transfer_record_id or istv_number
        const key = row.transfer_record_id
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
    const match = transferGroups.find((g) => g.recordId === recordId)
    if (match) {
      setDestinationWarehouseId(match.firstRow.destination_warehouse_id || '')
      // Populate lines with remaining quantities
      const newLines = match.rows.map((r) => ({
        item_id: r.item_id,
        quantity: String(r.remaining_quantity),
        maxRemaining: Number(r.remaining_quantity),
        remarks: `Received against ${r.istv_number}`,
      }))
      setLines(newLines.length > 0 ? newLines : [{ item_id: '', quantity: '1', remarks: '' }])
    }
  }

  // Pre-select if initialIstvId provided
  useEffect(() => {
    if (initialIstvId && transferGroups.length > 0) {
      handleSelectTransferGroup(initialIstvId)
    }
  }, [initialIstvId, transferGroups])

  const addLine = () => {
    setLines([...lines, { item_id: '', quantity: '1', remarks: '' }])
  }

  const removeLine = (idx: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== idx))
    }
  }

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
    for (const line of lines) {
      if (!line.item_id) {
        setErrorMessage('All lines must have a selected Item SKU.')
        return
      }
      const qty = parseFloat(line.quantity)
      if (isNaN(qty) || qty <= 0) {
        setErrorMessage('All receiving quantities must be greater than zero.')
        return
      }
      if (line.maxRemaining !== undefined && qty > line.maxRemaining) {
        setErrorMessage(`Received quantity (${qty}) exceeds remaining in-transit quantity (${line.maxRemaining}). Over-receiving is not allowed (ADR-005).`)
        return
      }
    }

    // Check unique items (ADR-006)
    const itemIds = lines.map((l) => l.item_id)
    if (new Set(itemIds).size !== itemIds.length) {
      setErrorMessage('Each item can only appear once in a voucher (ADR-006).')
      return
    }

    // If selectedTransferId is a recordId from report, we need the actual istv_transaction_id
    // But in our backend, ISTRVCreate expects istv_transaction_id
    // Let's resolve istv_transaction_id from the transfer report:
    // If the selected transfer record matched, we can find the ISTV ID, or use selectedTransferId directly
    let targetIstvId = selectedTransferId
    const matchedGroup = transferGroups.find((g) => g.recordId === selectedTransferId)
    if (matchedGroup) {
      // In report, istv_number is stored. The transfer_record_id might be distinct from istv_transaction_id
      // Let's check backend report: In backend report: `transfer_record_id = tr.id`, but we also need `istv_transaction_id = tr.istv_transaction_id`
      targetIstvId = matchedGroup.firstRow.transfer_record_id
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
    setLines([{ item_id: '', quantity: '1', remarks: '' }])
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
              Acknowledge and receive in-transit shipments at destination store. Automatically closes transit state and adds IN stock to destination warehouse.
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
                    {f.istv_number} — {f.source_warehouse_code} &rarr; {f.destination_warehouse_code} ({f.plate_no || 'No Plate'} / {f.driver_name || 'Driver'}) — {group.rows.length} item(s)
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
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-teal-500 focus:outline-hidden disabled:bg-slate-100"
            >
              <option value="">Select Destination Warehouse...</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-700">Receiving Remarks / Notes</label>
            <input
              type="text"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="Goods condition, container seal intact, etc."
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
              <p className="text-xs text-slate-500">Partial receiving supported. Over-receiving strictly rejected (ADR-005)</p>
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
            {lines.map((line, idx) => (
              <div key={idx} className="flex flex-wrap sm:flex-nowrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/60 p-3.5">
                <div className="flex-1 min-w-[220px]">
                  <label className="block text-[11px] font-medium text-slate-500">Item SKU *</label>
                  <select
                    value={line.item_id}
                    onChange={(e) => {
                      const updated = [...lines]
                      updated[idx].item_id = e.target.value
                      setLines(updated)
                    }}
                    required
                    disabled={isLoadingItems}
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white focus:border-teal-500 focus:outline-hidden"
                  >
                    <option value="">{isLoadingItems ? 'Loading catalog...' : 'Select SKU...'}</option>
                    {items.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.item_code} — {i.description}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="w-36">
                  <label className="block text-[11px] font-medium text-slate-500">
                    Receive Qty {line.maxRemaining !== undefined ? `(Max ${line.maxRemaining})` : ''} *
                  </label>
                  <input
                    type="number"
                    min="0.0001"
                    max={line.maxRemaining}
                    step="any"
                    value={line.quantity}
                    onChange={(e) => {
                      const updated = [...lines]
                      updated[idx].quantity = e.target.value
                      setLines(updated)
                    }}
                    required
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-teal-500 focus:outline-hidden"
                  />
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
                    placeholder="Condition / Bay"
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white focus:border-teal-500 focus:outline-hidden"
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
            ))}
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between border-t border-slate-200 pt-5">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <ShieldAlert className="h-4 w-4 text-teal-600" />
            <span>Updates transit records and credits destination warehouse stock (ADR-005)</span>
          </div>
          <button
            type="submit"
            disabled={createISTRVMutation.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-teal-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-teal-500 disabled:opacity-50 transition-colors"
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
