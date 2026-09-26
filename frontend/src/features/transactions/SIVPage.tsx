import React, { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { ArrowUpFromLine, Plus, Trash2, ShieldAlert, Loader2, AlertTriangle, ArrowLeft } from 'lucide-react'
import { useWarehouses, useItems } from '@/features/inventory/useInventoryData'
import {
  useProjects,
  useCreateSIV,
  extractErrorMessage,
} from './useTransactionData'
import { VoucherSuccessCard } from './VoucherSuccessCard'
import type { Transaction } from '@/types'

export const SIVPage: React.FC = () => {
  const [searchParams] = useSearchParams()
  const initialWarehouseId = searchParams.get('warehouse_id') || ''
  const initialItemId = searchParams.get('item_id') || ''

  const { data: warehouses = [], isLoading: isLoadingWarehouses } = useWarehouses()
  const { data: projects = [], isLoading: isLoadingProjects } = useProjects()
  const { data: itemsData, isLoading: isLoadingItems } = useItems({ limit: 1000 })
  const items = itemsData?.items || []

  const [warehouseId, setWarehouseId] = useState(initialWarehouseId)
  const [projectId, setProjectId] = useState('')
  const [requestedFrom, setRequestedFrom] = useState('')
  const [projectDept, setProjectDept] = useState('')
  const [requestedNo, setRequestedNo] = useState('')
  const [sivNo, setSivNo] = useState('')
  const [materialSummary, setMaterialSummary] = useState('')
  const [issuedByName, setIssuedByName] = useState('')
  const [checkedByName, setCheckedByName] = useState('')
  const [receivedByName, setReceivedByName] = useState('')
  const [approvedByName, setApprovedByName] = useState('')
  const [transactionDate, setTransactionDate] = useState(
    new Date().toISOString().split('T')[0]
  )
  const [remarks, setRemarks] = useState('')
  const [lines, setLines] = useState([
    { item_id: initialItemId, quantity: '1', unit: 'PCS', remarks: '' },
  ])
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [postedTransaction, setPostedTransaction] = useState<Transaction | null>(null)

  const createSIVMutation = useCreateSIV()

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

    if (!warehouseId) {
      setErrorMessage('Please select an issuing warehouse.')
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
        requested_from: requestedFrom.trim() || null,
        project_dept: projectDept.trim() || null,
        requested_no: requestedNo.trim() || null,
        siv_no: sivNo.trim() || null,
        material_summary: materialSummary.trim() || null,
        issued_by_name: issuedByName.trim() || null,
        checked_by_name: checkedByName.trim() || null,
        received_by_name: receivedByName.trim() || null,
        approved_by_name: approvedByName.trim() || null,
        remarks: remarks.trim() || null,
        lines: lines.map((l) => ({
          item_id: l.item_id,
          quantity: parseFloat(l.quantity),
          unit: l.unit.trim(),
          remarks: l.remarks.trim() || undefined,
        })),
      }

      const res = await createSIVMutation.mutateAsync(payload)
      setPostedTransaction(res)
    } catch (err) {
      setErrorMessage(extractErrorMessage(err))
    }
  }

  const handleReset = () => {
    setPostedTransaction(null)
    setRequestedFrom('')
    setProjectDept('')
    setRequestedNo('')
    setSivNo('')
    setMaterialSummary('')
    setRemarks('')
    setLines([{ item_id: '', quantity: '1', unit: 'PCS', remarks: '' }])
    setErrorMessage(null)
  }

  if (postedTransaction) {
    return (
      <div className="mx-auto max-w-4xl py-6">
        <VoucherSuccessCard
          transaction={postedTransaction}
          title="Store Issue Voucher (SIV)"
          onReset={handleReset}
        />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-indigo-100 p-2.5 text-indigo-700 shadow-xs">
            <ArrowUpFromLine className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Store Issue Voucher (SIV)
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Issue inventory to project sites or operational departments. Atomically validates available stock and decrements balances.
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
            <label className="block text-xs font-semibold text-slate-700">Issuing Warehouse *</label>
            <select
              value={warehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
              required
              disabled={isLoadingWarehouses}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-hidden"
            >
              <option value="">{isLoadingWarehouses ? 'Loading warehouses...' : 'Select Warehouse...'}</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Target Project / Job</label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              disabled={isLoadingProjects}
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-hidden"
            >
              <option value="">{isLoadingProjects ? 'Loading projects...' : 'General / Departmental'}</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} — {p.name}
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
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Department / Section</label>
            <input
              type="text"
              value={projectDept}
              onChange={(e) => setProjectDept(e.target.value)}
              placeholder="e.g. Civil Engineering / Site Phase 2"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Requested By Person / Entity</label>
            <input
              type="text"
              value={requestedFrom}
              onChange={(e) => setRequestedFrom(e.target.value)}
              placeholder="e.g. Site Supervisor Bekele"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Store Issue Voucher (SIV) #</label>
            <input
              type="text"
              value={sivNo}
              onChange={(e) => setSivNo(e.target.value)}
              placeholder="e.g. SIV-2026-0891"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Requisition / Request Ref #</label>
            <input
              type="text"
              value={requestedNo}
              onChange={(e) => setRequestedNo(e.target.value)}
              placeholder="e.g. REQ-ENG-402"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-hidden"
            />
          </div>

          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-700">Material Summary</label>
            <input
              type="text"
              value={materialSummary}
              onChange={(e) => setMaterialSummary(e.target.value)}
              placeholder="Brief summary of issued items e.g. Reinforcement steel for foundation grid"
              className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-hidden"
            />
          </div>
        </div>

        {/* Signatories section */}
        <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-3">
            Authorization & Signatory Tracking
          </h4>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="block text-[11px] font-medium text-slate-500">Issued By</label>
              <input
                type="text"
                value={issuedByName}
                onChange={(e) => setIssuedByName(e.target.value)}
                placeholder="Storekeeper name"
                className="mt-1 block w-full rounded-md border border-slate-300 py-1.5 px-2.5 text-xs bg-white focus:border-indigo-500 focus:outline-hidden"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500">Checked By</label>
              <input
                type="text"
                value={checkedByName}
                onChange={(e) => setCheckedByName(e.target.value)}
                placeholder="Auditor/Supervisor name"
                className="mt-1 block w-full rounded-md border border-slate-300 py-1.5 px-2.5 text-xs bg-white focus:border-indigo-500 focus:outline-hidden"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500">Received By</label>
              <input
                type="text"
                value={receivedByName}
                onChange={(e) => setReceivedByName(e.target.value)}
                placeholder="Recipient name"
                className="mt-1 block w-full rounded-md border border-slate-300 py-1.5 px-2.5 text-xs bg-white focus:border-indigo-500 focus:outline-hidden"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500">Approved By</label>
              <input
                type="text"
                value={approvedByName}
                onChange={(e) => setApprovedByName(e.target.value)}
                placeholder="Project manager name"
                className="mt-1 block w-full rounded-md border border-slate-300 py-1.5 px-2.5 text-xs bg-white focus:border-indigo-500 focus:outline-hidden"
              />
            </div>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700">Remarks / Operational Notes</label>
          <input
            type="text"
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
            placeholder="Optional comments regarding site destination or transport..."
            className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-hidden"
          />
        </div>

        {/* Lines */}
        <div className="border-t border-slate-200 pt-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Issued Line Items</h3>
              <p className="text-xs text-slate-500">Sufficient stock must exist in the issuing warehouse (ADR-002)</p>
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
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white focus:border-indigo-500 focus:outline-hidden"
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
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-indigo-500 focus:outline-hidden"
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
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white font-mono focus:border-indigo-500 focus:outline-hidden"
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
                    placeholder="Work unit or site location"
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-xs bg-white focus:border-indigo-500 focus:outline-hidden"
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
            <ShieldAlert className="h-4 w-4 text-emerald-600" />
            <span>Dual-write ledger entry will be posted atomically (ADR-001)</span>
          </div>
          <button
            type="submit"
            disabled={createSIVMutation.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500 disabled:opacity-50 transition-colors"
          >
            {createSIVMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Posting SIV...</span>
              </>
            ) : (
              <span>Post SIV Transaction</span>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}

export default SIVPage
