import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Undo2, Plus, Trash2, ShieldAlert, Loader2, AlertTriangle, ArrowLeft } from 'lucide-react'
import { useWarehouses, useItems } from '@/features/inventory/useInventoryData'
import {
  useProjects,
  useTransactions,
  useCreateSRV,
  extractErrorMessage,
} from './useTransactionData'
import { VoucherSuccessCard } from './VoucherSuccessCard'
import type { Transaction } from '@/types'

export const SRVPage: React.FC = () => {
  const { data: warehouses = [], isLoading: isLoadingWarehouses } = useWarehouses()
  const { data: projects = [], isLoading: isLoadingProjects } = useProjects()
  const { data: itemsData, isLoading: isLoadingItems } = useItems({ limit: 1000 })
  const items = itemsData?.items || []

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
  const [lines, setLines] = useState<Array<{
    item_id: string
    quantity: string
    unit: string
    remarks: string
  }>>([{ item_id: '', quantity: '1', unit: 'PCS', remarks: '' }])

  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [postedTransaction, setPostedTransaction] = useState<Transaction | null>(null)

  const createSRVMutation = useCreateSRV()

  // Handle selecting an SIV from the list
  const handleSelectSIV = (sivId: string) => {
    setReferenceSivId(sivId)
    const match = sivTransactions.find((s) => s.id === sivId)
    if (match) {
      if (match.warehouse_id) setWarehouseId(match.warehouse_id)
      if (match.project_id) setProjectId(match.project_id)
      if (match.lines && match.lines.length > 0) {
        setLines(
          match.lines.map((l) => ({
            item_id: l.item_id,
            quantity: String(l.quantity),
            unit: l.unit || 'PCS',
            remarks: `Returned from ${match.transaction_number}`,
          }))
        )
      }
    }
  }

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
    setLines([...lines, { item_id: '', quantity: '1', unit: 'PCS', remarks: '' }])
  }

  const removeLine = (idx: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== idx))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!referenceSivId) {
      setErrorMessage('A referenced Store Issue Voucher (SIV) ID is required.')
      return
    }

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
        setErrorMessage('All return quantities must be greater than zero.')
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
        reference_siv_id: referenceSivId,
        warehouse_id: warehouseId,
        project_id: projectId || null,
        transaction_date: transactionDate,
        remarks: remarks.trim() || null,
        lines: lines.map((l) => ({
          item_id: l.item_id,
          quantity: parseFloat(l.quantity),
          unit: l.unit.trim(),
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
    setLines([{ item_id: '', quantity: '1', unit: 'PCS', remarks: '' }])
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
    <div className="mx-auto max-w-4xl space-y-6">
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
              Process returns of unused/surplus items back to inventory against an originating SIV voucher. Increments stock on hand with an IN movement.
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
                  : 'Select prior SIV voucher...'}
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
              placeholder="UUID if not in dropdown"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm font-mono text-xs focus:border-rose-500 focus:outline-hidden"
            />
          </div>

          <div className="sm:col-span-3">
            <label className="block text-xs font-semibold text-slate-700">Return Reason / Justification</label>
            <input
              type="text"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="e.g. Unused surplus cement returned after foundation completion"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-rose-500 focus:outline-hidden"
            />
          </div>
        </div>

        {/* Selected SIV summary banner */}
        {selectedSIV && (
          <div className="rounded-xl border border-rose-200 bg-rose-50/50 p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-rose-800 mb-2">
              Referenced SIV Details: {selectedSIV.transaction_number}
            </h4>
            <div className="grid grid-cols-2 gap-2 text-xs text-rose-900 sm:grid-cols-4">
              <div>
                <span className="text-rose-600 block">Issued Date:</span>
                <strong>{selectedSIV.transaction_date}</strong>
              </div>
              <div>
                <span className="text-rose-600 block">Department:</span>
                <strong>{selectedSIV.project_dept || 'N/A'}</strong>
              </div>
              <div>
                <span className="text-rose-600 block">Requisition #:</span>
                <strong>{selectedSIV.requested_no || 'N/A'}</strong>
              </div>
              <div>
                <span className="text-rose-600 block">Issued Lines:</span>
                <strong>{selectedSIV.lines?.length || 0} line(s)</strong>
              </div>
            </div>
          </div>
        )}

        {/* Lines */}
        <div className="border-t border-slate-200 pt-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Returned Items</h3>
              <p className="text-xs text-slate-500">Return quantity cannot exceed originally issued quantity</p>
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
                    onChange={(e) => handleItemChange(idx, e.target.value)}
                    required
                    disabled={isLoadingItems}
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white focus:border-rose-500 focus:outline-hidden"
                  >
                    <option value="">{isLoadingItems ? 'Loading catalog...' : 'Select SKU...'}</option>
                    {items.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.item_code} — {i.description}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="w-28">
                  <label className="block text-[11px] font-medium text-slate-500">Return Qty *</label>
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
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-rose-500 focus:outline-hidden"
                  />
                </div>

                <div className="w-24">
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
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-rose-500 focus:outline-hidden"
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
                    placeholder="Condition / Packaging"
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white focus:border-rose-500 focus:outline-hidden"
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
            <ShieldAlert className="h-4 w-4 text-rose-600" />
            <span>Dual-write ledger entry will be posted atomically with reference audit (ADR-001)</span>
          </div>
          <button
            type="submit"
            disabled={createSRVMutation.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-rose-500 disabled:opacity-50 transition-colors"
          >
            {createSRVMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Posting SRV...</span>
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
