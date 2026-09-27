import React, { useState, useRef, useEffect, useMemo } from 'react'
import {
  Upload,
  FileSpreadsheet,
  AlertTriangle,
  CheckCircle2,
  X,
  Loader2,
  RotateCcw,
  Check,
  Search,
  ArrowRight,
  FileText,
  Layers,
  AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'
import { extractErrorMessage } from '@/features/transactions/useTransactionData'
import {
  useStageItemMaster,
  useCommitItemMaster,
} from '../useInventoryData'
import type {
  ImportBatchPreviewResponse,
  CommitBatchResponse,
  ImportErrorItem,
} from '@/types'

interface ImportItemsModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

type ModalPhase = 'upload' | 'preview' | 'success'

export const ImportItemsModal: React.FC<ImportItemsModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { hasRole } = useAuth()
  const isAuthorized = hasRole('ADMIN', 'INVENTORY_MANAGER')

  const [phase, setPhase] = useState<ModalPhase>('upload')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'errors' | 'items'>('errors')
  const [errorSearchQuery, setErrorSearchQuery] = useState('')
  const [errorFilterCode, setErrorFilterCode] = useState<string>('ALL')

  const [previewData, setPreviewData] = useState<ImportBatchPreviewResponse | null>(null)
  const [commitResult, setCommitResult] = useState<CommitBatchResponse | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const stageMutation = useStageItemMaster()
  const commitMutation = useCommitItemMaster()

  // Reset state when opening/closing
  useEffect(() => {
    if (!isOpen) {
      setPhase('upload')
      setSelectedFile(null)
      setDragActive(false)
      setErrorMessage(null)
      setActiveTab('errors')
      setErrorSearchQuery('')
      setErrorFilterCode('ALL')
      setPreviewData(null)
      setCommitResult(null)
    }
  }, [isOpen])

  // Close on Escape key press if not committing
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !commitMutation.isPending && !stageMutation.isPending) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, commitMutation.isPending, stageMutation.isPending, onClose])

  if (!isOpen) return null

  // File drag & drop handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const validateAndSetFile = (file: File) => {
    const validExtensions = ['.xlsx', '.xls', '.csv']
    const hasValidExt = validExtensions.some((ext) =>
      file.name.toLowerCase().endsWith(ext)
    )
    if (!hasValidExt) {
      setErrorMessage('Please upload a valid Excel workbook (.xlsx, .xls) or CSV (.csv) file.')
      setSelectedFile(null)
      return
    }
    setErrorMessage(null)
    setSelectedFile(file)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0])
    }
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0])
    }
  }

  const handleStageFile = async () => {
    if (!selectedFile) return
    setErrorMessage(null)
    try {
      const data = await stageMutation.mutateAsync(selectedFile)
      setPreviewData(data)
      // Switch active tab based on error presence
      if (data.errors && data.errors.length > 0) {
        setActiveTab('errors')
      } else {
        setActiveTab('items')
      }
      setPhase('preview')
    } catch (err: any) {
      setErrorMessage(extractErrorMessage(err))
    }
  }

  const handleCommitBatch = async () => {
    if (!previewData?.batch.id) return
    setErrorMessage(null)
    try {
      const res = await commitMutation.mutateAsync(previewData.batch.id)
      setCommitResult(res)
      setPhase('success')
      if (onSuccess) {
        onSuccess()
      }
    } catch (err: any) {
      setErrorMessage(extractErrorMessage(err))
    }
  }

  const handleResetToUpload = () => {
    setPhase('upload')
    setSelectedFile(null)
    setErrorMessage(null)
    setPreviewData(null)
    setCommitResult(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  // Filtered errors for interactive errors table
  const uniqueErrorCodes = useMemo(() => {
    if (!previewData?.errors) return []
    const codes = new Set(previewData.errors.map((e) => e.error_code))
    return Array.from(codes)
  }, [previewData?.errors])

  const filteredErrors = useMemo(() => {
    if (!previewData?.errors) return []
    return previewData.errors.filter((err: ImportErrorItem) => {
      const matchesCode =
        errorFilterCode === 'ALL' || err.error_code === errorFilterCode
      const query = errorSearchQuery.toLowerCase().trim()
      if (!query) return matchesCode

      const matchesSearch =
        err.row_number.toString().includes(query) ||
        (err.column_name && err.column_name.toLowerCase().includes(query)) ||
        (err.raw_value && err.raw_value.toLowerCase().includes(query)) ||
        err.error_code.toLowerCase().includes(query) ||
        err.error_message.toLowerCase().includes(query)

      return matchesCode && matchesSearch
    })
  }, [previewData?.errors, errorFilterCode, errorSearchQuery])

  // Formatting helper
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
  }

  const getErrorCodeBadgeColor = (code: string) => {
    switch (code) {
      case 'UNKNOWN_CATEGORY':
        return 'bg-amber-100 text-amber-800 border-amber-300'
      case 'MISSING_CODE':
      case 'MISSING_DESCRIPTION':
        return 'bg-rose-100 text-rose-800 border-rose-300'
      case 'MISSING_UOM':
        return 'bg-purple-100 text-purple-800 border-purple-300'
      case 'DUPLICATE_CODE':
        return 'bg-red-100 text-red-800 border-red-300'
      default:
        return 'bg-slate-100 text-slate-800 border-slate-300'
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto"
    >
      <div className="relative w-full max-w-4xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-100 text-sky-700">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Item Master Catalog Import
              </h2>
              <p className="text-xs text-slate-500">
                Upload spreadsheets (.xlsx, .csv) to stage, validate, and atomically commit new SKUs.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={stageMutation.isPending || commitMutation.isPending}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition-colors disabled:opacity-50"
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Global Error Banner */}
        {errorMessage && (
          <div className="mx-6 mt-4 p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-rose-900">Operation Error</h4>
              <p className="text-xs text-rose-700 mt-0.5">{errorMessage}</p>
            </div>
            <button
              type="button"
              onClick={() => setErrorMessage(null)}
              className="text-rose-500 hover:text-rose-800"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Body content based on phase */}
        <div className="p-6 overflow-y-auto flex-1">
          {/* Permission warning if user is not ADMIN or INVENTORY_MANAGER */}
          {!isAuthorized ? (
            <div className="p-8 text-center space-y-3">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-amber-700">
                <AlertTriangle className="h-6 w-6" />
              </div>
              <h3 className="text-base font-semibold text-slate-900">
                Restricted Action
              </h3>
              <p className="text-sm text-slate-500 max-w-md mx-auto">
                Only Administrators and Inventory Managers have authorization to stage and commit Item Master imports.
              </p>
              <div className="pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-200"
                >
                  Close
                </button>
              </div>
            </div>
          ) : phase === 'upload' ? (
            <div className="space-y-6">
              {/* Dropzone */}
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  'border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3',
                  dragActive
                    ? 'border-sky-500 bg-sky-50/50'
                    : 'border-slate-300 hover:border-sky-400 bg-slate-50/50'
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx, .xls, .csv"
                  onChange={handleFileInputChange}
                  className="hidden"
                />
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white shadow-xs border border-slate-200 text-sky-600">
                  <Upload className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Click to upload or drag & drop spreadsheet
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    Microsoft Excel (.xlsx, .xls) or Comma-Separated Values (.csv) up to 25 MB
                  </p>
                </div>
                <div className="inline-flex items-center gap-1.5 text-xs text-slate-600 bg-white border border-slate-200 rounded-md px-3 py-1 font-mono">
                  <span>Columns: inventory id, description, category, unit measurment</span>
                </div>
              </div>

              {/* Selected File Card */}
              {selectedFile && (
                <div className="flex items-center justify-between p-4 rounded-xl border border-sky-200 bg-sky-50/60">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-sky-600 text-white">
                      <FileSpreadsheet className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-900 truncate">
                        {selectedFile.name}
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatBytes(selectedFile.size)} • Ready for parsing
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedFile(null)
                      if (fileInputRef.current) fileInputRef.current.value = ''
                    }}
                    className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-white"
                    title="Remove file"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}

              {/* Expected Format Guidelines */}
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                  Standard Import Format Rules
                </h4>
                <ul className="text-xs text-slate-600 space-y-1.5 list-disc pl-4">
                  <li>
                    <span className="font-semibold text-slate-800">Item Code:</span> Unique SKU identifier (e.g. <code className="bg-slate-100 px-1 py-0.5 rounded">01-CM-00001</code>). Trailing blank draft rows are automatically ignored.
                  </li>
                  <li>
                    <span className="font-semibold text-slate-800">Categories:</span> Matches master codes or names (e.g. <code className="bg-slate-100 px-1 py-0.5 rounded">01</code>, <code className="bg-slate-100 px-1 py-0.5 rounded">01-CM</code>, or <code className="bg-slate-100 px-1 py-0.5 rounded">Cement & Aggregates</code>).
                  </li>
                  <li>
                    <span className="font-semibold text-slate-800">Unit of Measurement:</span> Expected standard units (e.g. <code className="bg-slate-100 px-1 py-0.5 rounded">BAG</code>, <code className="bg-slate-100 px-1 py-0.5 rounded">PCS</code>, <code className="bg-slate-100 px-1 py-0.5 rounded">KG</code>). Missing units will be flagged for review.
                  </li>
                </ul>
              </div>
            </div>
          ) : phase === 'preview' && previewData ? (
            <div className="space-y-6">
              {/* Metrics Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-500">Total Rows</span>
                    <Layers className="h-4 w-4 text-slate-400" />
                  </div>
                  <p className="text-xl font-bold text-slate-900 mt-1">
                    {previewData.batch.total_rows.toLocaleString()}
                  </p>
                  <p className="text-[10px] text-slate-400 truncate mt-0.5">
                    {previewData.batch.file_name}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/50">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-emerald-800">Valid Rows</span>
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  </div>
                  <p className="text-xl font-bold text-emerald-900 mt-1">
                    {previewData.batch.valid_rows.toLocaleString()}
                  </p>
                  <p className="text-[10px] text-emerald-700 mt-0.5">
                    Ready to commit
                  </p>
                </div>

                <div className="p-3.5 rounded-xl border border-rose-200 bg-rose-50/50">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-rose-800">Error Rows</span>
                    <AlertTriangle className="h-4 w-4 text-rose-600" />
                  </div>
                  <p className="text-xl font-bold text-rose-900 mt-1">
                    {previewData.batch.error_rows.toLocaleString()}
                  </p>
                  <p className="text-[10px] text-rose-700 mt-0.5">
                    {previewData.batch.error_rows === 0 ? 'Zero errors' : 'Will be skipped'}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-500">Batch Code</span>
                    <FileText className="h-4 w-4 text-slate-400" />
                  </div>
                  <p className="text-xs font-mono font-bold text-slate-900 mt-2 truncate">
                    {previewData.batch.batch_number}
                  </p>
                  <span className="inline-block mt-0.5 px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-100 text-sky-800">
                    {previewData.batch.status}
                  </span>
                </div>
              </div>

              {/* Status Banner */}
              {previewData.batch.error_rows === 0 ? (
                <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50 flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-semibold text-emerald-900">
                      Spreadsheet Validated Successfully
                    </h4>
                    <p className="text-xs text-emerald-700 mt-0.5">
                      All {previewData.batch.valid_rows} rows passed category matching and SKU code validation. You can safely commit these items into the live catalog.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-xl border border-amber-200 bg-amber-50 flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-semibold text-amber-900">
                      Validation Issues Detected ({previewData.batch.error_rows} rows)
                    </h4>
                    <p className="text-xs text-amber-700 mt-0.5">
                      Review the table below. Committing will insert all{' '}
                      <span className="font-bold">{previewData.batch.valid_rows} valid items</span> while excluding invalid rows.
                    </p>
                  </div>
                </div>
              )}

              {/* Interactive Tabs */}
              <div className="space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200">
                  <div className="flex gap-4">
                    {previewData.errors.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setActiveTab('errors')}
                        className={cn(
                          'pb-2.5 text-xs font-bold transition-colors border-b-2 flex items-center gap-1.5',
                          activeTab === 'errors'
                            ? 'border-rose-600 text-rose-700'
                            : 'border-transparent text-slate-500 hover:text-slate-800'
                        )}
                      >
                        <AlertTriangle className="h-3.5 w-3.5" />
                        <span>Validation Errors ({previewData.errors.length})</span>
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setActiveTab('items')}
                      className={cn(
                        'pb-2.5 text-xs font-bold transition-colors border-b-2 flex items-center gap-1.5',
                        activeTab === 'items'
                          ? 'border-sky-600 text-sky-700'
                          : 'border-transparent text-slate-500 hover:text-slate-800'
                      )}
                    >
                      <Check className="h-3.5 w-3.5" />
                      <span>Valid Items Preview ({previewData.valid_items_sample.length} sample)</span>
                    </button>
                  </div>
                </div>

                {/* Tab: Errors */}
                {activeTab === 'errors' && previewData.errors.length > 0 && (
                  <div className="space-y-3">
                    {/* Filter & Search Bar for Errors */}
                    <div className="flex flex-col sm:flex-row gap-2">
                      <div className="relative flex-1">
                        <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
                        <input
                          type="text"
                          value={errorSearchQuery}
                          onChange={(e) => setErrorSearchQuery(e.target.value)}
                          placeholder="Filter errors by row, field, or text..."
                          className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:border-sky-500"
                        />
                      </div>
                      <select
                        value={errorFilterCode}
                        onChange={(e) => setErrorFilterCode(e.target.value)}
                        className="text-xs rounded-lg border border-slate-300 px-3 py-1.5 bg-white text-slate-700"
                      >
                        <option value="ALL">All Error Codes ({previewData.errors.length})</option>
                        {uniqueErrorCodes.map((code) => (
                          <option key={code} value={code}>
                            {code}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Errors Table */}
                    <div className="rounded-xl border border-slate-200 overflow-hidden max-h-64 overflow-y-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-100 text-slate-700 sticky top-0 font-semibold border-b border-slate-200">
                          <tr>
                            <th className="py-2 px-3 w-16">Row #</th>
                            <th className="py-2 px-3 w-28">Column</th>
                            <th className="py-2 px-3 w-36">Raw Value</th>
                            <th className="py-2 px-3 w-36">Error Code</th>
                            <th className="py-2 px-3">Description</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 bg-white font-normal">
                          {filteredErrors.length === 0 ? (
                            <tr>
                              <td colSpan={5} className="py-4 text-center text-slate-400">
                                No errors match your filter criteria.
                              </td>
                            </tr>
                          ) : (
                            filteredErrors.map((err) => (
                              <tr key={err.id} className="hover:bg-slate-50">
                                <td className="py-2 px-3 font-mono font-semibold text-slate-900">
                                  {err.row_number}
                                </td>
                                <td className="py-2 px-3 font-medium text-slate-700">
                                  {err.column_name || '—'}
                                </td>
                                <td className="py-2 px-3">
                                  <span className="font-mono text-[11px] bg-slate-100 text-slate-800 px-1.5 py-0.5 rounded border border-slate-200 max-w-[140px] truncate inline-block">
                                    {err.raw_value ? String(err.raw_value) : 'EMPTY'}
                                  </span>
                                </td>
                                <td className="py-2 px-3">
                                  <span
                                    className={cn(
                                      'inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold border',
                                      getErrorCodeBadgeColor(err.error_code)
                                    )}
                                  >
                                    {err.error_code}
                                  </span>
                                </td>
                                <td className="py-2 px-3 text-slate-600">
                                  {err.error_message}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Tab: Valid Items Preview */}
                {activeTab === 'items' && (
                  <div className="rounded-xl border border-slate-200 overflow-hidden max-h-64 overflow-y-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-100 text-slate-700 sticky top-0 font-semibold border-b border-slate-200">
                        <tr>
                          <th className="py-2 px-3 w-32">SKU Code</th>
                          <th className="py-2 px-3">Description</th>
                          <th className="py-2 px-3 w-28">Category</th>
                          <th className="py-2 px-3 w-20">Unit</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {previewData.valid_items_sample.length === 0 ? (
                          <tr>
                            <td colSpan={4} className="py-4 text-center text-slate-400">
                              No valid items staged in this batch.
                            </td>
                          </tr>
                        ) : (
                          previewData.valid_items_sample.map((item, idx) => (
                            <tr key={idx} className="hover:bg-slate-50">
                              <td className="py-2 px-3 font-mono font-semibold text-sky-700">
                                {item.item_code}
                              </td>
                              <td className="py-2 px-3 text-slate-900 font-medium truncate max-w-xs">
                                {item.description}
                              </td>
                              <td className="py-2 px-3 text-slate-600">
                                {item.category_code || item.category_id || '—'}
                              </td>
                              <td className="py-2 px-3">
                                <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[10px] border border-slate-200">
                                  {item.default_unit}
                                </span>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          ) : phase === 'success' && commitResult ? (
            <div className="py-8 text-center space-y-4">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 shadow-xs">
                <CheckCircle2 className="h-8 w-8" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-900">
                  Item Master Import Committed
                </h3>
                <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
                  {commitResult.message}
                </p>
              </div>

              <div className="mx-auto max-w-sm rounded-xl border border-slate-200 bg-slate-50 p-4 text-left space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Batch Number:</span>
                  <span className="font-mono font-semibold text-slate-800">
                    {commitResult.batch_number}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">SKUs Created:</span>
                  <span className="font-bold text-emerald-700">
                    {commitResult.imported_count} items
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Catalog Status:</span>
                  <span className="font-semibold text-slate-800">Active & Searchable</span>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200 bg-slate-50">
          {phase === 'upload' ? (
            <>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!selectedFile || stageMutation.isPending || !isAuthorized}
                onClick={handleStageFile}
                className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-sky-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {stageMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Parsing & Validating...</span>
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4" />
                    <span>Stage & Validate Spreadsheet</span>
                  </>
                )}
              </button>
            </>
          ) : phase === 'preview' ? (
            <>
              <button
                type="button"
                onClick={handleResetToUpload}
                disabled={commitMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span>Upload Another File</span>
              </button>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={commitMutation.isPending}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={
                    !previewData ||
                    previewData.batch.valid_rows === 0 ||
                    commitMutation.isPending ||
                    !isAuthorized
                  }
                  onClick={handleCommitBatch}
                  className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {commitMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Committing to Catalog...</span>
                    </>
                  ) : (
                    <>
                      <Check className="h-4 w-4" />
                      <span>
                        Confirm & Commit {previewData?.batch.valid_rows.toLocaleString()} Items
                      </span>
                    </>
                  )}
                </button>
              </div>
            </>
          ) : (
            <div className="w-full flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-sky-500"
              >
                <span>Close & View Catalog</span>
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
