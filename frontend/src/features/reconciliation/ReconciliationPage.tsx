import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  ClipboardCheck,
  Search,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
  Lock,
  Loader2,
  RotateCcw,
  Layers,
  ArrowDownLeft,
  ArrowUpRight,
  FileCheck,
  RefreshCw,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useWarehouses } from '@/features/inventory/useInventoryData'
import { extractErrorMessage } from '@/features/transactions/useTransactionData'
import {
  useCountSheet,
  usePreviewVariance,
  useCommitReconciliation,
} from './useReconciliationData'
import type {
  CountSheetItem,
  ReconciliationPreviewResponse,
  ReconciliationCommitResponse,
} from '@/types'

export const ReconciliationPage: React.FC = () => {
  const { user } = useAuth()
  const isAuthorized = user?.role === 'ADMIN' || user?.role === 'INVENTORY_MANAGER'

  const { data: warehouses = [], isLoading: isLoadingWarehouses } = useWarehouses()

  const [warehouseId, setWarehouseId] = useState('')
  const [countDate, setCountDate] = useState(
    new Date().toISOString().split('T')[0]
  )
  const [countRef, setCountRef] = useState('')
  const [batchRemarks, setBatchRemarks] = useState('')
  const [adjustmentReason, setAdjustmentReason] = useState('')
  const [activeStep, setActiveStep] = useState<'sheet' | 'preview' | 'success'>('sheet')

  // Search filter inside count table
  const [itemSearch, setItemSearch] = useState('')

  // Editable count items
  const [countRows, setCountRows] = useState<
    Array<{
      item_id: string
      item_code: string
      item_description: string
      category_name: string
      unit: string
      system_qty: number
      counted_qty: string
      remarks: string
    }>
  >([])

  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [previewData, setPreviewData] = useState<ReconciliationPreviewResponse | null>(null)
  const [commitResult, setCommitResult] = useState<ReconciliationCommitResponse | null>(null)

  // Query count sheet
  const {
    data: countSheetData,
    isLoading: isLoadingCountSheet,
    refetch: refetchCountSheet,
  } = useCountSheet(warehouseId || undefined)

  const previewMutation = usePreviewVariance()
  const commitMutation = useCommitReconciliation()

  // Generate default count reference when warehouse or date changes
  useEffect(() => {
    if (warehouseId && warehouses.length > 0) {
      const wh = warehouses.find((w) => w.id === warehouseId)
      const dateCode = countDate.replace(/-/g, '')
      const whCode = wh ? wh.code : 'STORE'
      setCountRef(`COUNT-${dateCode}-${whCode}`)
    }
  }, [warehouseId, countDate, warehouses])

  // Populate countRows when countSheetData arrives
  useEffect(() => {
    if (countSheetData?.items) {
      setCountRows(
        countSheetData.items.map((item: CountSheetItem) => {
          const sysQty = Number(item.system_quantity_on_hand ?? item.system_quantity ?? 0)
          return {
            item_id: item.item_id,
            item_code: item.item_code,
            item_description: item.item_description,
            category_name: item.category_name,
            unit: item.unit,
            system_qty: sysQty,
            counted_qty: String(sysQty), // Defaults to system qty for faster spot audit
            remarks: '',
          }
        })
      )
    }
  }, [countSheetData])

  const handlePrefillSystem = () => {
    setCountRows((prev) =>
      prev.map((r) => ({
        ...r,
        counted_qty: String(r.system_qty),
      }))
    )
  }

  const handleCalculatePreview = async () => {
    setErrorMessage(null)

    if (!warehouseId) {
      setErrorMessage('Please select an audit warehouse.')
      return
    }

    if (!countRef.trim()) {
      setErrorMessage('A count batch reference tag is required.')
      return
    }

    if (countRows.length === 0) {
      setErrorMessage('Count sheet contains no items. Please select a warehouse with active inventory.')
      return
    }

    // Validate quantities
    for (const r of countRows) {
      const val = parseFloat(r.counted_qty)
      if (isNaN(val) || val < 0) {
        setErrorMessage(`Invalid count for SKU ${r.item_code}: quantity must be >= 0.`)
        return
      }
    }

    try {
      const payload = {
        warehouse_id: warehouseId,
        count_date: countDate,
        count_reference: countRef.trim(),
        remarks: batchRemarks.trim() || undefined,
        counts: countRows.map((r) => ({
          item_id: r.item_id,
          counted_quantity: parseFloat(r.counted_qty),
          remarks: r.remarks.trim() || undefined,
        })),
      }

      const res = await previewMutation.mutateAsync(payload)
      setPreviewData(res)
      setAdjustmentReason(`Physical inventory count reconciliation ${countRef.trim()}`)
      setActiveStep('preview')
    } catch (err) {
      setErrorMessage(extractErrorMessage(err))
    }
  }

  const handleCommitReconciliation = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!isAuthorized) {
      setErrorMessage('Access Denied: Only Admin and Inventory Manager roles can post stock reconciliations.')
      return
    }

    if (!adjustmentReason.trim()) {
      setErrorMessage('A mandatory reconciliation audit reason is required.')
      return
    }

    try {
      const payload = {
        warehouse_id: warehouseId,
        count_date: countDate,
        count_reference: countRef.trim(),
        adjustment_reason: adjustmentReason.trim(),
        counts: countRows.map((r) => ({
          item_id: r.item_id,
          counted_quantity: parseFloat(r.counted_qty),
          remarks: r.remarks.trim() || undefined,
        })),
      }

      const res = await commitMutation.mutateAsync(payload)
      setCommitResult(res)
      setActiveStep('success')
    } catch (err) {
      setErrorMessage(extractErrorMessage(err))
    }
  }

  const handleResetWorkflow = () => {
    setActiveStep('sheet')
    setPreviewData(null)
    setCommitResult(null)
    setAdjustmentReason('')
    setErrorMessage(null)
    refetchCountSheet()
  }

  // Filter count sheet items by search term
  const filteredCountRows = countRows.filter((r) => {
    if (!itemSearch.trim()) return true
    const q = itemSearch.toLowerCase().trim()
    return (
      r.item_code.toLowerCase().includes(q) ||
      r.item_description.toLowerCase().includes(q) ||
      r.category_name.toLowerCase().includes(q)
    )
  })

  // Variances from preview
  const variancesList = previewData?.variances ?? previewData?.lines ?? []
  const surplusCount = previewData?.surplus_items_count ?? previewData?.surplus_count ?? 0
  const deficitCount = previewData?.deficit_items_count ?? previewData?.deficit_count ?? 0
  const matchedCount = previewData?.matched_items_count ?? previewData?.matched_count ?? 0
  const totalCounted = previewData?.total_items_counted ?? 0
  const hasVariances = surplusCount > 0 || deficitCount > 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-2.5 text-white shadow-xs">
            <ClipboardCheck className="h-6 w-6 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Physical Stock Count & Reconciliation
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Audit count sheet entry, live variance calculation, and automated dual-write reconciliation adjustments.
            </p>
          </div>
        </div>

        {!isAuthorized && (
          <div className="inline-flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2 text-xs font-semibold text-amber-800">
            <Lock className="h-4 w-4 text-amber-600" />
            <span>Role Restricted: View Only (Admin/Manager required to post)</span>
          </div>
        )}
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 animate-in fade-in">
          <AlertTriangle className="h-5 w-5 shrink-0 text-red-600 mt-0.5" />
          <div>
            <span className="font-semibold">Reconciliation Error:</span> {errorMessage}
          </div>
        </div>
      )}

      {/* Post-Commit Success Screen */}
      {activeStep === 'success' && commitResult && (
        <div className="mx-auto max-w-2xl rounded-2xl border border-emerald-200 bg-white p-8 shadow-lg text-center animate-in fade-in">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 mx-auto mb-4">
            <CheckCircle2 className="h-10 w-10" />
          </div>

          <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-700 border border-emerald-200 mb-2 inline-block">
            RECONCILIATION COMPLETED ATOMICALLY
          </span>

          <h2 className="text-2xl font-bold text-slate-900 mt-1">
            Physical Inventory Reconciled
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {commitResult.message}
          </p>

          <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50/80 p-5 text-left text-xs space-y-2">
            <div className="flex justify-between">
              <span className="text-slate-500">Audit Count Reference:</span>
              <strong className="font-mono text-slate-900">{commitResult.count_reference}</strong>
            </div>
            {commitResult.transaction_number && (
              <div className="flex justify-between">
                <span className="text-slate-500">Compensating Voucher:</span>
                <strong className="font-mono text-emerald-700 font-bold">
                  {commitResult.transaction_number}
                </strong>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-slate-500">Adjusted Items Count:</span>
              <strong className="text-slate-900 font-mono">
                {commitResult.adjusted_lines_count} line(s)
              </strong>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={handleResetWorkflow}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition-colors"
            >
              <RotateCcw className="h-4 w-4 text-slate-400" />
              <span>New Count Audit</span>
            </button>

            <Link
              to="/transactions"
              className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-slate-800 transition-colors"
            >
              <span>View Transaction Ledger</span>
              <ArrowRight className="h-4 w-4" />
            </Link>

            <Link
              to="/reports/trial-balance"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-100 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-200 transition-colors"
            >
              <span>Check Trial Balance</span>
            </Link>
          </div>
        </div>
      )}

      {/* Step 1: Count Sheet Entry */}
      {activeStep === 'sheet' && (
        <div className="space-y-6">
          {/* Warehouse & Reference Selection Bar */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Audit Batch Parameters
            </h3>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Audit Warehouse *
                </label>
                <select
                  value={warehouseId}
                  onChange={(e) => setWarehouseId(e.target.value)}
                  disabled={isLoadingWarehouses}
                  className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs focus:border-slate-500 focus:outline-hidden"
                >
                  <option value="">Select Audit Store...</option>
                  {warehouses.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.code} — {w.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Count Batch Reference *
                </label>
                <input
                  type="text"
                  value={countRef}
                  onChange={(e) => setCountRef(e.target.value)}
                  placeholder="e.g. COUNT-20260921-BATCH01"
                  className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs font-mono focus:border-slate-500 focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Physical Count Date *
                </label>
                <input
                  type="date"
                  value={countDate}
                  onChange={(e) => setCountDate(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs focus:border-slate-500 focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Batch Remarks / Audit Tag
                </label>
                <input
                  type="text"
                  value={batchRemarks}
                  onChange={(e) => setBatchRemarks(e.target.value)}
                  placeholder="e.g. Q3 Wall-to-wall stocktake"
                  className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs focus:border-slate-500 focus:outline-hidden"
                />
              </div>
            </div>
          </div>

          {/* Count Sheet Table */}
          {warehouseId ? (
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
              {/* Table Toolbar */}
              <div className="flex flex-wrap items-center justify-between border-b border-slate-200 bg-slate-50/70 p-4 gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-700">
                    Active Catalog Items ({countRows.length})
                  </span>
                  {isLoadingCountSheet && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative w-64">
                    <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
                    <input
                      type="text"
                      value={itemSearch}
                      onChange={(e) => setItemSearch(e.target.value)}
                      placeholder="Filter SKU or description..."
                      className="w-full rounded-lg border border-slate-300 py-1.5 pl-8 pr-2.5 text-xs bg-white focus:outline-hidden"
                    />
                  </div>

                  <button
                    type="button"
                    onClick={handlePrefillSystem}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition-colors"
                  >
                    Prefill All from System
                  </button>

                  <button
                    type="button"
                    onClick={() => refetchCountSheet()}
                    className="rounded-lg border border-slate-200 bg-white p-1.5 text-slate-500 hover:bg-slate-100 transition-colors"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              {/* Data Table */}
              <div className="overflow-x-auto max-h-[550px]">
                <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                  <thead className="bg-slate-50/90 font-semibold text-slate-600 sticky top-0 z-10 shadow-xs">
                    <tr>
                      <th className="py-3 px-4">SKU Code</th>
                      <th className="py-3 px-4">Description</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Unit</th>
                      <th className="py-3 px-4 text-right">System Recorded</th>
                      <th className="py-3 px-4 text-right w-44">Physical Counted Qty *</th>
                      <th className="py-3 px-4">Line Notes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {isLoadingCountSheet ? (
                      <tr>
                        <td colSpan={7} className="py-16 text-center text-slate-400">
                          <Loader2 className="mx-auto h-7 w-7 animate-spin text-slate-400 mb-2" />
                          <span>Generating warehouse count sheet...</span>
                        </td>
                      </tr>
                    ) : filteredCountRows.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-12 text-center text-slate-400">
                          <Layers className="mx-auto h-8 w-8 text-slate-300 mb-2" />
                          <p className="font-semibold text-slate-600">No matching items</p>
                        </td>
                      </tr>
                    ) : (
                      filteredCountRows.map((item) => {
                        const originalIdx = countRows.findIndex((r) => r.item_id === item.item_id)
                        const countedVal = parseFloat(item.counted_qty)
                        const hasDiff = !isNaN(countedVal) && countedVal !== item.system_qty

                        return (
                          <tr
                            key={item.item_id}
                            className={`transition-colors ${
                              hasDiff ? 'bg-amber-50/40 hover:bg-amber-50/70' : 'hover:bg-slate-50/70'
                            }`}
                          >
                            <td className="py-3 px-4 font-mono font-bold text-slate-900">
                              {item.item_code}
                            </td>
                            <td className="py-3 px-4 text-slate-800 max-w-xs truncate">
                              {item.item_description}
                            </td>
                            <td className="py-3 px-4 text-slate-500 whitespace-nowrap">
                              {item.category_name}
                            </td>
                            <td className="py-3 px-4 font-mono text-slate-600 whitespace-nowrap">
                              {item.unit}
                            </td>
                            <td className="py-3 px-4 text-right font-mono font-medium text-slate-700 whitespace-nowrap">
                              {item.system_qty.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </td>
                            <td className="py-3 px-4 text-right">
                              <input
                                type="number"
                                min="0"
                                step="any"
                                value={item.counted_qty}
                                onChange={(e) => {
                                  const updated = [...countRows]
                                  if (originalIdx !== -1) {
                                    updated[originalIdx].counted_qty = e.target.value
                                    setCountRows(updated)
                                  }
                                }}
                                className={`w-32 rounded-lg border py-1 px-2 text-right text-xs font-mono focus:outline-hidden ${
                                  hasDiff
                                    ? 'border-amber-400 bg-amber-50/60 font-bold text-amber-900'
                                    : 'border-slate-300 bg-white text-slate-900'
                                }`}
                              />
                            </td>
                            <td className="py-3 px-4">
                              <input
                                type="text"
                                value={item.remarks}
                                onChange={(e) => {
                                  const updated = [...countRows]
                                  if (originalIdx !== -1) {
                                    updated[originalIdx].remarks = e.target.value
                                    setCountRows(updated)
                                  }
                                }}
                                placeholder="Condition / Shelf"
                                className="w-full rounded-lg border border-slate-200 py-1 px-2 text-xs bg-white focus:outline-hidden"
                              />
                            </td>
                          </tr>
                        )
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {/* Bottom Action Strip */}
              <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/80 p-4">
                <span className="text-xs text-slate-500">
                  Total items counted: <strong>{countRows.length}</strong>
                </span>

                <button
                  type="button"
                  onClick={handleCalculatePreview}
                  disabled={previewMutation.isPending || countRows.length === 0}
                  className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-slate-800 disabled:opacity-50 transition-colors"
                >
                  {previewMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Calculating Variances...</span>
                    </>
                  ) : (
                    <>
                      <span>Calculate & Preview Variances</span>
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border-2 border-dashed border-slate-200 p-12 text-center">
              <ClipboardCheck className="mx-auto h-10 w-10 text-slate-300 mb-2" />
              <p className="font-semibold text-slate-700">Select an Audit Warehouse</p>
              <p className="text-xs text-slate-400 mt-0.5">
                Choose a store above to generate its physical inventory count sheet.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Variance Analysis & Commit */}
      {activeStep === 'preview' && previewData && (
        <form onSubmit={handleCommitReconciliation} className="space-y-6 animate-in fade-in">
          {/* Summary Metric Strip */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Total Counted
              </span>
              <p className="mt-1 text-2xl font-bold font-mono text-slate-900">
                {totalCounted}
              </p>
            </div>

            <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4 shadow-xs">
              <span className="text-xs font-semibold uppercase tracking-wider text-emerald-700">
                Exact Matches
              </span>
              <p className="mt-1 text-2xl font-bold font-mono text-emerald-700">
                {matchedCount}
              </p>
            </div>

            <div className="rounded-2xl border border-sky-200 bg-sky-50/50 p-4 shadow-xs">
              <span className="text-xs font-semibold uppercase tracking-wider text-sky-700">
                Surplus (+IN)
              </span>
              <p className="mt-1 text-2xl font-bold font-mono text-sky-700">
                {surplusCount}
              </p>
            </div>

            <div className="rounded-2xl border border-rose-200 bg-rose-50/50 p-4 shadow-xs">
              <span className="text-xs font-semibold uppercase tracking-wider text-rose-700">
                Deficit (-OUT)
              </span>
              <p className="mt-1 text-2xl font-bold font-mono text-rose-700">
                {deficitCount}
              </p>
            </div>
          </div>

          {/* Zero Variance Banner if all matched */}
          {!hasVariances && (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-900 flex items-center gap-3">
              <CheckCircle2 className="h-6 w-6 shrink-0 text-emerald-600" />
              <div>
                <p className="text-sm font-bold">All items perfectly match system inventory!</p>
                <p className="text-xs text-emerald-700 mt-0.5">
                  No discrepancy adjustments required. Submitting will record the audit log for count batch <strong>{previewData.count_reference}</strong>.
                </p>
              </div>
            </div>
          )}

          {/* Variances Table */}
          {hasVariances && (
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
              <div className="border-b border-slate-200 bg-slate-50/80 p-4">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                  Discrepancies Requiring Reconciliation Adjustment
                </h3>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                  <thead className="bg-slate-50/90 font-semibold text-slate-600 uppercase text-[11px]">
                    <tr>
                      <th className="py-3 px-4">SKU Code</th>
                      <th className="py-3 px-4">Description</th>
                      <th className="py-3 px-4 text-right">System Qty</th>
                      <th className="py-3 px-4 text-right">Counted Qty</th>
                      <th className="py-3 px-4 text-right">Variance</th>
                      <th className="py-3 px-4 text-center">Compensating Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {variancesList
                      .filter((v) => Number(v.variance_quantity) !== 0)
                      .map((v) => {
                        const varianceVal = Number(v.variance_quantity)
                        const isSurplus = varianceVal > 0

                        return (
                          <tr key={v.item_id} className="hover:bg-slate-50/70">
                            <td className="py-3 px-4 font-mono font-bold text-slate-900">
                              {v.item_code}
                            </td>
                            <td className="py-3 px-4 text-slate-800">
                              {v.item_description}
                            </td>
                            <td className="py-3 px-4 text-right font-mono text-slate-700">
                              {Number(v.system_quantity).toLocaleString(undefined, { minimumFractionDigits: 2 })} {v.unit}
                            </td>
                            <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                              {Number(v.counted_quantity).toLocaleString(undefined, { minimumFractionDigits: 2 })} {v.unit}
                            </td>
                            <td className="py-3 px-4 text-right font-mono font-bold">
                              {isSurplus ? (
                                <span className="text-sky-600">
                                  +{varianceVal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </span>
                              ) : (
                                <span className="text-rose-600">
                                  {varianceVal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-4 text-center">
                              {isSurplus ? (
                                <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2.5 py-0.5 text-xs font-semibold text-sky-700 border border-sky-200">
                                  <ArrowDownLeft className="h-3 w-3" />
                                  <span>+IN Surplus Voucher</span>
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-semibold text-rose-700 border border-rose-200">
                                  <ArrowUpRight className="h-3 w-3" />
                                  <span>-OUT Deficit Voucher</span>
                                </span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Mandatory Reason Card & Submit Controls */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700">
                Mandatory Reconciliation Reason * <span className="font-normal text-slate-400">(Required for audit log & adjustment voucher)</span>
              </label>
              <textarea
                rows={2}
                value={adjustmentReason}
                onChange={(e) => setAdjustmentReason(e.target.value)}
                required
                minLength={3}
                placeholder="Document purpose of adjustment e.g. Q3 2026 scheduled physical count reconciliation"
                className="mt-1 block w-full rounded-xl border border-slate-300 py-2 px-3 text-xs focus:border-slate-500 focus:outline-hidden"
              />
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-t border-slate-100 pt-4">
              <button
                type="button"
                onClick={() => setActiveStep('sheet')}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
              >
                <span>&larr; Back to Count Sheet</span>
              </button>

              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <ShieldCheck className="h-4 w-4 text-emerald-600" />
                  <span>Dual-write compensating adjustment executed atomically</span>
                </div>

                <button
                  type="submit"
                  disabled={commitMutation.isPending || !isAuthorized}
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-6 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-emerald-500 disabled:opacity-50 transition-colors"
                >
                  {commitMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Posting Reconciliation...</span>
                    </>
                  ) : (
                    <>
                      <FileCheck className="h-4 w-4" />
                      <span>Post Reconciled Adjustments</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </form>
      )}
    </div>
  )
}

export default ReconciliationPage
