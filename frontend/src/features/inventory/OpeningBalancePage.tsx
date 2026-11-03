import React, { useState, useRef, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  FileSpreadsheet,
  Plus,
  History,
  Upload,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Trash2,
  Download,
  Loader2,
  RotateCcw,
  PackageCheck,
  ArrowRight,
  Search,
} from 'lucide-react'
import {
  useWarehouses,
  useItems,
  useStageInitialStock,
  useCommitInitialStock,
  useCreateManualOpeningBalance,
  useInitialStockBatches,
  useOpeningBalanceTransactions,
} from './useInventoryData'
import { useProjects, extractErrorMessage } from '@/features/transactions/useTransactionData'
import type {
  InitialStockBatchPreviewResponse,
  CommitInitialStockResponse,
  Transaction,
} from '@/types'

export const OpeningBalancePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'excel' | 'manual' | 'history'>('excel')

  // Common data
  const { data: rawWarehouses = [], isLoading: isLoadingWarehouses } = useWarehouses()
  const warehouses = useMemo(() => rawWarehouses.filter((w) => w.is_active !== false), [rawWarehouses])
  const { data: rawProjects = [], isLoading: isLoadingProjects } = useProjects()
  const projects = useMemo(() => rawProjects.filter((p) => p.is_active !== false), [rawProjects])
  const { data: itemsData } = useItems({ limit: 1000 })
  const items = itemsData?.items || []

  // ---------------------------------------------------------------------------
  // Tab 1: Bulk Excel Import State
  // ---------------------------------------------------------------------------
  const [excelWarehouseId, setExcelWarehouseId] = useState('')
  const [excelProjectId, setExcelProjectId] = useState('')
  const [excelDate, setExcelDate] = useState(new Date().toISOString().split('T')[0])
  const [excelRemarks, setExcelRemarks] = useState('')
  const [excelFile, setExcelFile] = useState<File | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [excelErrorMessage, setExcelErrorMessage] = useState<string | null>(null)
  const [previewData, setPreviewData] = useState<InitialStockBatchPreviewResponse | null>(null)
  const [previewSubTab, setPreviewSubTab] = useState<'valid' | 'issues'>('valid')
  const [commitResult, setCommitResult] = useState<CommitInitialStockResponse | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const stageMutation = useStageInitialStock()
  const commitMutation = useCommitInitialStock()

  // ---------------------------------------------------------------------------
  // Tab 2: Manual Entry State
  // ---------------------------------------------------------------------------
  const [manualWarehouseId, setManualWarehouseId] = useState('')
  const [manualProjectId, setManualProjectId] = useState('')
  const [manualDate, setManualDate] = useState(new Date().toISOString().split('T')[0])
  const [manualRemarks, setManualRemarks] = useState('')
  const [manualLines, setManualLines] = useState<Array<{
    item_id: string
    quantity: string
    unit: string
    unit_price: string
    remarks: string
  }>>([
    { item_id: '', quantity: '1', unit: '', unit_price: '0.00', remarks: '' },
  ])
  const [manualErrorMessage, setManualErrorMessage] = useState<string | null>(null)
  const [postedTransaction, setPostedTransaction] = useState<Transaction | null>(null)

  const manualMutation = useCreateManualOpeningBalance()

  // ---------------------------------------------------------------------------
  // Tab 3: History State
  // ---------------------------------------------------------------------------
  const { data: batches = [], isLoading: isLoadingBatches } = useInitialStockBatches()
  const { data: transactions = [], isLoading: isLoadingTransactions } = useOpeningBalanceTransactions()
  const [historySubTab, setHistorySubTab] = useState<'batches' | 'vouchers'>('batches')
  const [historySearch, setHistorySearch] = useState('')

  // ---------------------------------------------------------------------------
  // Excel File Handlers
  // ---------------------------------------------------------------------------
  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0]
      validateAndSetFile(file)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0])
    }
  }

  const validateAndSetFile = (file: File) => {
    setExcelErrorMessage(null)
    const validExts = ['.xlsx', '.xls', '.csv']
    const hasValidExt = validExts.some((ext) => file.name.toLowerCase().endsWith(ext))
    if (!hasValidExt) {
      setExcelErrorMessage('Invalid file format. Please upload an .xlsx, .xls, or .csv file.')
      return
    }
    if (file.size > 20 * 1024 * 1024) {
      setExcelErrorMessage('File size exceeds the 20MB limit.')
      return
    }
    setExcelFile(file)
  }

  const handleStageExcel = async () => {
    if (!excelWarehouseId) {
      setExcelErrorMessage('Please select a target Warehouse/Bin location before uploading.')
      return
    }
    if (!excelFile) {
      setExcelErrorMessage('Please select a file to stage.')
      return
    }

    setExcelErrorMessage(null)
    try {
      const res = await stageMutation.mutateAsync({
        file: excelFile,
        warehouse_id: excelWarehouseId,
        project_id: excelProjectId || undefined,
        transaction_date: excelDate,
        remarks: excelRemarks || 'Opening balance import',
      })
      setPreviewData(res)
      if (res.errors && res.errors.length > 0 && res.valid_rows_sample.length === 0) {
        setPreviewSubTab('issues')
      } else {
        setPreviewSubTab('valid')
      }
    } catch (err: any) {
      setExcelErrorMessage(extractErrorMessage(err))
    }
  }

  const handleCommitBatch = async () => {
    if (!previewData?.batch.id) return
    setExcelErrorMessage(null)
    try {
      const res = await commitMutation.mutateAsync(previewData.batch.id)
      setCommitResult(res)
      setPreviewData(null)
      setExcelFile(null)
    } catch (err: any) {
      setExcelErrorMessage(extractErrorMessage(err))
    }
  }

  const handleDownloadTemplate = () => {
    // Generate clean CSV template with 4 columns: inventory id, quantity, unit measurment, unit price
    const sampleItems = items.slice(0, 3)
    let csvContent = 'inventory id,quantity,unit measurment,unit price\n'
    if (sampleItems.length > 0) {
      sampleItems.forEach((item, idx) => {
        const qty = (idx + 1) * 100
        const price = (idx + 1) * 250.5
        csvContent += `${item.item_code},${qty},${item.default_unit || 'PCS'},${price.toFixed(2)}\n`
      })
    } else {
      csvContent += '01-CM-00001,500,BAG,450.00\n02-ST-00001,200,PCS,120.00\n'
    }

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'opening_stock_template.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // ---------------------------------------------------------------------------
  // Manual Entry Handlers
  // ---------------------------------------------------------------------------
  const handleAddManualLine = () => {
    setManualLines((prev) => [
      ...prev,
      { item_id: '', quantity: '1', unit: '', unit_price: '0.00', remarks: '' },
    ])
  }

  const handleRemoveManualLine = (index: number) => {
    setManualLines((prev) => prev.filter((_, idx) => idx !== index))
  }

  const handleManualLineChange = (
    index: number,
    field: 'item_id' | 'quantity' | 'unit' | 'unit_price' | 'remarks',
    value: string
  ) => {
    setManualLines((prev) => {
      const updated = [...prev]
      updated[index] = { ...updated[index], [field]: value }
      if (field === 'item_id') {
        const selected = items.find((i) => i.id === value)
        if (selected) {
          updated[index].unit = selected.default_unit || 'PCS'
        }
      }
      return updated
    })
  }

  const handlePostManual = async (e: React.FormEvent) => {
    e.preventDefault()
    setManualErrorMessage(null)

    if (!manualWarehouseId) {
      setManualErrorMessage('Please select a target Warehouse/Bin.')
      return
    }

    if (manualLines.length === 0) {
      setManualErrorMessage('Please add at least one item line.')
      return
    }

    // Check line validity
    const itemIds = new Set<string>()
    for (let i = 0; i < manualLines.length; i++) {
      const line = manualLines[i]
      if (!line.item_id) {
        setManualErrorMessage(`Line ${i + 1}: Item is required.`)
        return
      }
      if (itemIds.has(line.item_id)) {
        setManualErrorMessage(`Line ${i + 1}: Duplicate item selected. Each item can appear only once (ADR-006).`)
        return
      }
      itemIds.add(line.item_id)

      const qty = parseFloat(line.quantity)
      if (isNaN(qty) || qty <= 0) {
        setManualErrorMessage(`Line ${i + 1}: Quantity must be strictly positive.`)
        return
      }

      const price = parseFloat(line.unit_price)
      if (isNaN(price) || price < 0) {
        setManualErrorMessage(`Line ${i + 1}: Unit price must be greater than or equal to 0.`)
        return
      }
    }

    try {
      const payload = {
        warehouse_id: manualWarehouseId,
        project_id: manualProjectId || null,
        transaction_date: manualDate,
        remarks: manualRemarks || 'Manual Opening Balance',
        lines: manualLines.map((l) => ({
          item_id: l.item_id,
          quantity: parseFloat(l.quantity),
          unit: l.unit.trim() || 'PCS',
          unit_price: parseFloat(l.unit_price) || 0,
          remarks: l.remarks || null,
        })),
      }
      const res = await manualMutation.mutateAsync(payload)
      setPostedTransaction(res)
    } catch (err: any) {
      setManualErrorMessage(extractErrorMessage(err))
    }
  }

  // Live Manual Totals
  const manualTotals = useMemo(() => {
    let totalQty = 0
    let totalVal = 0
    manualLines.forEach((l) => {
      const q = parseFloat(l.quantity) || 0
      const p = parseFloat(l.unit_price) || 0
      totalQty += q
      totalVal += q * p
    })
    return { totalQty, totalVal }
  }, [manualLines])

  // Filtered History
  const filteredBatches = useMemo(() => {
    if (!historySearch.trim()) return batches
    const q = historySearch.toLowerCase()
    return batches.filter(
      (b) =>
        b.batch_number.toLowerCase().includes(q) ||
        b.file_name.toLowerCase().includes(q) ||
        b.status.toLowerCase().includes(q)
    )
  }, [batches, historySearch])

  const filteredTransactions = useMemo(() => {
    if (!historySearch.trim()) return transactions
    const q = historySearch.toLowerCase()
    return transactions.filter(
      (t) =>
        t.transaction_number.toLowerCase().includes(q) ||
        (t.remarks && t.remarks.toLowerCase().includes(q))
    )
  }, [transactions, historySearch])

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Opening Balance (Initial Stock)
            </h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
              Dual-Write Ledger
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Establish baseline inventory quantities with dual-write ledger atomicity (`ADR-001`, `ADR-002`, `ADR-003`).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/inventory"
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm transition-colors"
          >
            <PackageCheck className="w-4 h-4 text-slate-500" />
            View Balances
          </Link>
        </div>
      </div>

      {/* Mode Switcher Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-6" aria-label="Tabs">
          <button
            type="button"
            onClick={() => {
              setActiveTab('excel')
              setCommitResult(null)
              setPostedTransaction(null)
            }}
            className={`flex items-center gap-2 py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'excel'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            Bulk Excel / CSV Import
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab('manual')
              setCommitResult(null)
              setPostedTransaction(null)
            }}
            className={`flex items-center gap-2 py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'manual'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <Plus className="w-4 h-4" />
            Manual Entry Form
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab('history')
              setCommitResult(null)
              setPostedTransaction(null)
            }}
            className={`flex items-center gap-2 py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'history'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <History className="w-4 h-4" />
            Batches & History
          </button>
        </nav>
      </div>

      {/* ==================================================================== */}
      {/* TAB 1: BULK EXCEL IMPORT                                             */}
      {/* ==================================================================== */}
      {activeTab === 'excel' && (
        <div className="space-y-6">
          {commitResult ? (
            /* Post-Commit Success Screen */
            <div className="bg-white border border-emerald-200 rounded-xl p-8 shadow-sm text-center max-w-2xl mx-auto space-y-4">
              <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-10 h-10" />
              </div>
              <h2 className="text-xl font-bold text-slate-900">
                Opening Balance Successfully Posted!
              </h2>
              <p className="text-sm text-slate-600">
                {commitResult.message}
              </p>
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-left grid grid-cols-2 gap-4 text-sm mt-4">
                <div>
                  <span className="text-slate-500 block text-xs">Import Batch Number</span>
                  <span className="font-mono font-medium text-slate-800">{commitResult.batch_number}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-xs">Rows Committed</span>
                  <span className="font-semibold text-emerald-700">{commitResult.imported_rows} SKU lines</span>
                </div>
                <div className="col-span-2">
                  <span className="text-slate-500 block text-xs">Vouchers Created</span>
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {commitResult.transaction_numbers.map((txNum) => (
                      <span key={txNum} className="font-mono text-xs font-semibold px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded">
                        {txNum}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex justify-center gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setCommitResult(null)
                    setPreviewData(null)
                    setExcelFile(null)
                  }}
                  className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm"
                >
                  Import Another Batch
                </button>
                <Link
                  to="/inventory"
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-sm"
                >
                  Go to Inventory Balances
                </Link>
                <Link
                  to="/reports/trial-balance"
                  className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm"
                >
                  View in Trial Balance
                </Link>
              </div>
            </div>
          ) : !previewData ? (
            /* Upload & Configuration Form */
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">
                    Step 1: Target Location & Spreadsheet Upload
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Select target warehouse bin and upload the 4-column Opening Stock spreadsheet (`inventory id`, `quantity`, `unit measurment`, `unit price`).
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleDownloadTemplate}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors self-start"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download 4-Column Template
                </button>
              </div>

              {excelErrorMessage && (
                <div className="bg-rose-50 border border-rose-200 text-rose-800 text-sm p-3.5 rounded-lg flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-600 mt-0.5" />
                  <div>{excelErrorMessage}</div>
                </div>
              )}

              {/* Form Controls */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Target Warehouse / Bin Location <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={excelWarehouseId}
                    onChange={(e) => setExcelWarehouseId(e.target.value)}
                    className="w-full text-sm border-slate-300 rounded-lg shadow-sm focus:border-blue-500 focus:ring-blue-500 bg-white"
                    disabled={isLoadingWarehouses}
                  >
                    <option value="">-- Select Active Project Warehouse --</option>
                    {warehouses.map((wh) => (
                      <option key={wh.id} value={wh.id}>
                        {wh.code} - {wh.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Effective Opening Date <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={excelDate}
                    onChange={(e) => setExcelDate(e.target.value)}
                    className="w-full text-sm border-slate-300 rounded-lg shadow-sm focus:border-blue-500 focus:ring-blue-500 bg-white"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Linked Project Site (Optional)
                  </label>
                  <select
                    value={excelProjectId}
                    onChange={(e) => setExcelProjectId(e.target.value)}
                    className="w-full text-sm border-slate-300 rounded-lg shadow-sm focus:border-blue-500 focus:ring-blue-500 bg-white"
                    disabled={isLoadingProjects}
                  >
                    <option value="">-- No Specific Project --</option>
                    {projects.map((proj) => (
                      <option key={proj.id} value={proj.id}>
                        {proj.code} - {proj.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="md:col-span-3">
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Voucher Header Remarks (Optional)
                  </label>
                  <input
                    type="text"
                    value={excelRemarks}
                    onChange={(e) => setExcelRemarks(e.target.value)}
                    placeholder="e.g. Official Client Store Opening Stock Count 2026"
                    className="w-full text-sm border-slate-300 rounded-lg shadow-sm focus:border-blue-500 focus:ring-blue-500 bg-white"
                  />
                </div>
              </div>

              {/* Upload Drop Zone */}
              <div
                onDragOver={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  setDragActive(true)
                }}
                onDragLeave={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  setDragActive(false)
                }}
                onDrop={handleFileDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                  dragActive
                    ? 'border-blue-500 bg-blue-50/60'
                    : excelFile
                    ? 'border-emerald-400 bg-emerald-50/30'
                    : 'border-slate-300 hover:border-slate-400 bg-slate-50/50'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <div className="flex flex-col items-center justify-center space-y-3">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
                    excelFile ? 'bg-emerald-100 text-emerald-600' : 'bg-blue-100 text-blue-600'
                  }`}>
                    {excelFile ? <CheckCircle2 className="w-6 h-6" /> : <Upload className="w-6 h-6" />}
                  </div>
                  <div>
                    {excelFile ? (
                      <div>
                        <p className="text-sm font-semibold text-slate-800">{excelFile.name}</p>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {(excelFile.size / 1024).toFixed(1)} KB — Click or drag to replace
                        </p>
                      </div>
                    ) : (
                      <div>
                        <p className="text-sm font-semibold text-slate-800">
                          Click to upload or drag & drop 4-column Opening Stock file
                        </p>
                        <p className="text-xs text-slate-500 mt-1">
                          Supported formats: Excel (.xlsx, .xls) or CSV (.csv) up to 20MB
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Column Format Guidance Card */}
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-xs text-slate-600 space-y-2">
                <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                  <FileSpreadsheet className="w-4 h-4 text-blue-600" />
                  Expected 4-Column Layout
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 pt-1 font-mono">
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="font-bold text-blue-700 block text-[11px]">1. inventory id</span>
                    <span className="text-slate-500 text-[10px]">Item SKU (e.g. 01-CM-00001)</span>
                  </div>
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="font-bold text-blue-700 block text-[11px]">2. quantity</span>
                    <span className="text-slate-500 text-[10px]">Stock quantity strictly &gt; 0</span>
                  </div>
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="font-bold text-blue-700 block text-[11px]">3. unit measurment</span>
                    <span className="text-slate-500 text-[10px]">UOM (falls back to item UOM)</span>
                  </div>
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="font-bold text-blue-700 block text-[11px]">4. unit price</span>
                    <span className="text-slate-500 text-[10px]">Valuation cost (&ge; 0, opt)</span>
                  </div>
                </div>
              </div>

              {/* Action Bar */}
              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={handleStageExcel}
                  disabled={!excelWarehouseId || !excelFile || stageMutation.isPending}
                  className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-all"
                >
                  {stageMutation.isPending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Parsing & Validating...
                    </>
                  ) : (
                    <>
                      Validate & Preview Staged Opening Balance
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : (
            /* Staged Preview & Review Screen */
            <div className="space-y-6">
              {/* Staging Metrics Banner */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                  <span className="text-xs font-medium text-slate-500">Total Scanned Rows</span>
                  <div className="text-2xl font-bold text-slate-900 mt-1">{previewData.batch.total_rows}</div>
                  <span className="text-[11px] text-slate-400">File: {previewData.batch.file_name}</span>
                </div>

                <div className="bg-white border border-emerald-200 rounded-xl p-4 shadow-sm">
                  <span className="text-xs font-medium text-emerald-700">Valid Rows to Post</span>
                  <div className="text-2xl font-bold text-emerald-600 mt-1">{previewData.batch.valid_rows}</div>
                  <span className="text-[11px] text-emerald-600">Ready for atomic balance posting</span>
                </div>

                <div className="bg-white border border-amber-200 rounded-xl p-4 shadow-sm">
                  <span className="text-xs font-medium text-amber-700">Skipped / Issues</span>
                  <div className="text-2xl font-bold text-amber-600 mt-1">{previewData.batch.error_rows}</div>
                  <span className="text-[11px] text-amber-600">Duplicates or catalog mismatches</span>
                </div>

                <div className="bg-white border border-violet-200 rounded-xl p-4 shadow-sm">
                  <span className="text-xs font-medium text-violet-700">Estimated Total Value</span>
                  <div className="text-2xl font-bold text-violet-700 mt-1">
                    ETB {parseFloat(String(previewData.total_value || 0)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <span className="text-[11px] text-violet-600">Quantity &times; Unit Price</span>
                </div>
              </div>

              {excelErrorMessage && (
                <div className="bg-rose-50 border border-rose-200 text-rose-800 text-sm p-3.5 rounded-lg flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-600 mt-0.5" />
                  <div>{excelErrorMessage}</div>
                </div>
              )}

              {/* Informational Alert on Status */}
              {previewData.batch.status === 'VALIDATED' ? (
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 text-emerald-800 text-sm flex items-start gap-3">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold">Batch validated successfully!</span>{' '}
                    All {previewData.batch.valid_rows} rows are clean and ready to be posted as the authoritative opening balance in `{warehouses.find(w => w.id === excelWarehouseId)?.code}`.
                  </div>
                </div>
              ) : (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-amber-800 text-sm flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold">Partial Ingestion Warning:</span>{' '}
                    Some rows encountered validation errors or duplicate entries. Valid rows ({previewData.batch.valid_rows}) can still be confirmed and posted cleanly without double-counting.
                  </div>
                </div>
              )}

              {/* Sub-Tabs: Valid Lines vs Issues */}
              <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                <div className="flex border-b border-slate-200 px-6 pt-4 gap-4">
                  <button
                    type="button"
                    onClick={() => setPreviewSubTab('valid')}
                    className={`pb-3 text-sm font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                      previewSubTab === 'valid'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    Valid Stock Lines
                    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                      {previewData.valid_rows_sample.length}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setPreviewSubTab('issues')}
                    className={`pb-3 text-sm font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                      previewSubTab === 'issues'
                        ? 'border-rose-600 text-rose-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    Validation Issues / Skipped
                    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                      {previewData.errors.length}
                    </span>
                  </button>
                </div>

                {previewSubTab === 'valid' ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-50/80 text-slate-600 uppercase tracking-wider text-[11px] border-b border-slate-200">
                          <th className="py-2.5 px-4 font-semibold">Row</th>
                          <th className="py-2.5 px-4 font-semibold">Inventory ID / SKU</th>
                          <th className="py-2.5 px-4 font-semibold">Description</th>
                          <th className="py-2.5 px-4 font-semibold text-right">Quantity</th>
                          <th className="py-2.5 px-4 font-semibold">Unit</th>
                          <th className="py-2.5 px-4 font-semibold text-right">Unit Price</th>
                          <th className="py-2.5 px-4 font-semibold text-right">Total Price</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-slate-800">
                        {previewData.valid_rows_sample.length === 0 ? (
                          <tr>
                            <td colSpan={7} className="py-8 text-center text-slate-400">
                              No valid stock lines available to stage.
                            </td>
                          </tr>
                        ) : (
                          previewData.valid_rows_sample.map((r, idx) => (
                            <tr key={idx} className="hover:bg-slate-50/50">
                              <td className="py-2.5 px-4 text-slate-400 font-mono">#{r.row_number}</td>
                              <td className="py-2.5 px-4 font-mono font-medium text-blue-700">{r.item_code}</td>
                              <td className="py-2.5 px-4 text-slate-600 truncate max-w-xs">{r.item_description || '—'}</td>
                              <td className="py-2.5 px-4 text-right font-semibold text-slate-900">
                                {parseFloat(String(r.quantity)).toLocaleString()}
                              </td>
                              <td className="py-2.5 px-4 text-slate-500 font-medium">{r.unit}</td>
                              <td className="py-2.5 px-4 text-right text-slate-600">
                                {parseFloat(String(r.unit_price)).toFixed(2)}
                              </td>
                              <td className="py-2.5 px-4 text-right font-semibold text-slate-900">
                                {parseFloat(String(r.total_price)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-50/80 text-slate-600 uppercase tracking-wider text-[11px] border-b border-slate-200">
                          <th className="py-2.5 px-4 font-semibold">Row</th>
                          <th className="py-2.5 px-4 font-semibold">Column</th>
                          <th className="py-2.5 px-4 font-semibold">Raw Value</th>
                          <th className="py-2.5 px-4 font-semibold">Issue Code</th>
                          <th className="py-2.5 px-4 font-semibold">Description</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-slate-800">
                        {previewData.errors.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="py-8 text-center text-emerald-600 font-medium">
                              Zero validation issues found! All rows are clean.
                            </td>
                          </tr>
                        ) : (
                          previewData.errors.map((err, idx) => (
                            <tr key={idx} className="hover:bg-slate-50/50">
                              <td className="py-2.5 px-4 font-mono text-slate-400">#{err.row_number}</td>
                              <td className="py-2.5 px-4 font-medium text-slate-600">{err.column_name || '—'}</td>
                              <td className="py-2.5 px-4 font-mono text-slate-700">{err.raw_value || '—'}</td>
                              <td className="py-2.5 px-4">
                                <span className={`inline-flex px-2 py-0.5 rounded text-[11px] font-semibold ${
                                  err.error_code === 'ALREADY_EXISTS'
                                    ? 'bg-amber-100 text-amber-800'
                                    : err.error_code === 'DUPLICATE_IN_FILE'
                                    ? 'bg-purple-100 text-purple-800'
                                    : 'bg-rose-100 text-rose-800'
                                }`}>
                                  {err.error_code}
                                </span>
                              </td>
                              <td className="py-2.5 px-4 text-slate-600">{err.error_message}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Staging Action Bar */}
                <div className="bg-slate-50/80 px-6 py-4 border-t border-slate-200 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => {
                      setPreviewData(null)
                      setExcelErrorMessage(null)
                    }}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm transition-colors"
                  >
                    <RotateCcw className="w-4 h-4 text-slate-500" />
                    Reset & Upload Another File
                  </button>

                  <button
                    type="button"
                    onClick={handleCommitBatch}
                    disabled={previewData.batch.valid_rows === 0 || commitMutation.isPending}
                    className="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-all"
                  >
                    {commitMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Posting Opening Balance...
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        Confirm & Post Opening Balance ({previewData.batch.valid_rows} Lines)
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 2: MANUAL ENTRY FORM                                             */}
      {/* ==================================================================== */}
      {activeTab === 'manual' && (
        <div className="space-y-6">
          {postedTransaction ? (
            <div className="bg-white border border-emerald-200 rounded-xl p-8 shadow-sm text-center max-w-2xl mx-auto space-y-4">
              <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-10 h-10" />
              </div>
              <h2 className="text-xl font-bold text-slate-900">
                Opening Balance Voucher Posted!
              </h2>
              <p className="text-sm text-slate-600">
                Transaction voucher <span className="font-mono font-bold text-slate-800">{postedTransaction.transaction_number}</span> has been atomically committed into inventory balances and the append-only stock movement ledger.
              </p>
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-left grid grid-cols-2 gap-4 text-sm mt-4">
                <div>
                  <span className="text-slate-500 block text-xs">Transaction Number</span>
                  <span className="font-mono font-medium text-slate-800">{postedTransaction.transaction_number}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-xs">Transaction Type</span>
                  <span className="font-semibold text-blue-700">{postedTransaction.transaction_type} (Opening Balance)</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-xs">Total Lines</span>
                  <span className="font-semibold text-slate-800">{postedTransaction.lines?.length || 0} item lines</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-xs">Status</span>
                  <span className="inline-flex px-2 py-0.5 text-xs font-semibold rounded bg-emerald-100 text-emerald-800">
                    {postedTransaction.status}
                  </span>
                </div>
              </div>
              <div className="flex justify-center gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setPostedTransaction(null)
                    setManualLines([{ item_id: '', quantity: '1', unit: '', unit_price: '0.00', remarks: '' }])
                  }}
                  className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm"
                >
                  Create Another Voucher
                </button>
                <Link
                  to="/inventory"
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-sm"
                >
                  View in Inventory Balances
                </Link>
                <Link
                  to="/reports/trial-balance"
                  className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm"
                >
                  View in Trial Balance
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handlePostManual} className="space-y-6">
              {manualErrorMessage && (
                <div className="bg-rose-50 border border-rose-200 text-rose-800 text-sm p-3.5 rounded-lg flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-600 mt-0.5" />
                  <div>{manualErrorMessage}</div>
                </div>
              )}

              {/* Form Header Configuration */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
                <h2 className="text-lg font-semibold text-slate-900 border-b border-slate-100 pb-3">
                  Opening Balance Header
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Target Warehouse / Bin Location <span className="text-rose-500">*</span>
                    </label>
                    <select
                      value={manualWarehouseId}
                      onChange={(e) => setManualWarehouseId(e.target.value)}
                      className="w-full text-sm border-slate-300 rounded-lg shadow-sm focus:border-blue-500 focus:ring-blue-500 bg-white"
                      disabled={isLoadingWarehouses}
                      required
                    >
                      <option value="">-- Select Active Project Warehouse --</option>
                      {warehouses.map((wh) => (
                        <option key={wh.id} value={wh.id}>
                          {wh.code} - {wh.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Effective Date <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="date"
                      value={manualDate}
                      onChange={(e) => setManualDate(e.target.value)}
                      className="w-full text-sm border-slate-300 rounded-lg shadow-sm focus:border-blue-500 focus:ring-blue-500 bg-white"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Linked Project (Optional)
                    </label>
                    <select
                      value={manualProjectId}
                      onChange={(e) => setManualProjectId(e.target.value)}
                      className="w-full text-sm border-slate-300 rounded-lg shadow-sm focus:border-blue-500 focus:ring-blue-500 bg-white"
                      disabled={isLoadingProjects}
                    >
                      <option value="">-- No Specific Project --</option>
                      {projects.map((proj) => (
                        <option key={proj.id} value={proj.id}>
                          {proj.code} - {proj.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="md:col-span-3">
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Voucher Remarks (Optional)
                    </label>
                    <input
                      type="text"
                      value={manualRemarks}
                      onChange={(e) => setManualRemarks(e.target.value)}
                      placeholder="e.g. Initial store physical count sign-off"
                      className="w-full text-sm border-slate-300 rounded-lg shadow-sm focus:border-blue-500 focus:ring-blue-500 bg-white"
                    />
                  </div>
                </div>
              </div>

              {/* Dynamic Lines Table */}
              <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-slate-900">
                      Opening Balance Lines
                    </h2>
                    <p className="text-xs text-slate-500">
                      Item SKU, positive quantity, unit measurement, and unit price valuation.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleAddManualLine}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Item Line
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[11px] border-b border-slate-200">
                        <th className="py-2.5 px-3 w-12 text-center">#</th>
                        <th className="py-2.5 px-3 min-w-[240px]">Item Master SKU &amp; Name *</th>
                        <th className="py-2.5 px-3 w-28 text-right">Quantity *</th>
                        <th className="py-2.5 px-3 w-28">UOM</th>
                        <th className="py-2.5 px-3 w-32 text-right">Unit Price (ETB)</th>
                        <th className="py-2.5 px-3 w-36 text-right">Total (ETB)</th>
                        <th className="py-2.5 px-3">Line Remarks</th>
                        <th className="py-2.5 px-3 w-12 text-center">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-800">
                      {manualLines.map((line, idx) => {
                        const qtyNum = parseFloat(line.quantity) || 0
                        const priceNum = parseFloat(line.unit_price) || 0
                        const rowTotal = (qtyNum * priceNum).toFixed(2)

                        return (
                          <tr key={idx} className="hover:bg-slate-50/50">
                            <td className="py-2.5 px-3 text-center text-slate-400 font-mono">
                              {idx + 1}
                            </td>
                            <td className="py-2.5 px-3">
                              <select
                                value={line.item_id}
                                onChange={(e) => handleManualLineChange(idx, 'item_id', e.target.value)}
                                className="w-full text-xs border-slate-300 rounded shadow-sm focus:border-blue-500 focus:ring-blue-500 bg-white"
                                required
                              >
                                <option value="">-- Choose Item from Catalog --</option>
                                {items.map((item) => (
                                  <option key={item.id} value={item.id}>
                                    {item.item_code} - {item.description} ({item.default_unit})
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <input
                                type="number"
                                step="any"
                                min="0.0001"
                                value={line.quantity}
                                onChange={(e) => handleManualLineChange(idx, 'quantity', e.target.value)}
                                placeholder="1.0"
                                className="w-full text-xs border-slate-300 rounded text-right shadow-sm focus:border-blue-500 focus:ring-blue-500"
                                required
                              />
                            </td>
                            <td className="py-2.5 px-3">
                              <input
                                type="text"
                                value={line.unit}
                                onChange={(e) => handleManualLineChange(idx, 'unit', e.target.value)}
                                placeholder="UOM"
                                className="w-full text-xs border-slate-300 rounded shadow-sm focus:border-blue-500 focus:ring-blue-500 bg-slate-50"
                              />
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <input
                                type="number"
                                step="any"
                                min="0"
                                value={line.unit_price}
                                onChange={(e) => handleManualLineChange(idx, 'unit_price', e.target.value)}
                                placeholder="0.00"
                                className="w-full text-xs border-slate-300 rounded text-right shadow-sm focus:border-blue-500 focus:ring-blue-500"
                              />
                            </td>
                            <td className="py-2.5 px-3 text-right font-semibold text-slate-800">
                              {parseFloat(rowTotal).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </td>
                            <td className="py-2.5 px-3">
                              <input
                                type="text"
                                value={line.remarks}
                                onChange={(e) => handleManualLineChange(idx, 'remarks', e.target.value)}
                                placeholder="Notes..."
                                className="w-full text-xs border-slate-300 rounded shadow-sm focus:border-blue-500 focus:ring-blue-500"
                              />
                            </td>
                            <td className="py-2.5 px-3 text-center">
                              {manualLines.length > 1 && (
                                <button
                                  type="button"
                                  onClick={() => handleRemoveManualLine(idx)}
                                  className="text-slate-400 hover:text-rose-600 transition-colors p-1"
                                  title="Remove Line"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Live Summary Bar */}
                <div className="bg-slate-50/80 px-6 py-4 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div className="flex items-center gap-6 text-sm">
                    <div>
                      <span className="text-slate-500 text-xs">Total Lines: </span>
                      <span className="font-bold text-slate-800">{manualLines.length}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 text-xs">Total Units: </span>
                      <span className="font-bold text-slate-800">{manualTotals.totalQty.toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 text-xs">Total Valuation: </span>
                      <span className="font-bold text-violet-700">
                        ETB {manualTotals.totalVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={manualMutation.isPending}
                    className="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-all"
                  >
                    {manualMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Posting Opening Balance...
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        Post Opening Balance Voucher
                      </>
                    )}
                  </button>
                </div>
              </div>
            </form>
          )}
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 3: BATCHES & HISTORY                                             */}
      {/* ==================================================================== */}
      {activeTab === 'history' && (
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setHistorySubTab('batches')}
                  className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                    historySubTab === 'batches'
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  Excel Import Batches ({batches.length})
                </button>
                <button
                  type="button"
                  onClick={() => setHistorySubTab('vouchers')}
                  className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                    historySubTab === 'vouchers'
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  Posted Opening Vouchers ({transactions.length})
                </button>
              </div>

              <div className="relative w-full sm:w-64">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                  placeholder="Search batches / vouchers..."
                  className="w-full text-xs pl-9 pr-3 py-2 border-slate-300 rounded-lg shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>
            </div>

            {historySubTab === 'batches' ? (
              <div className="overflow-x-auto border border-slate-100 rounded-lg">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[11px] border-b border-slate-200">
                      <th className="py-2.5 px-4 font-semibold">Batch Number</th>
                      <th className="py-2.5 px-4 font-semibold">File Name</th>
                      <th className="py-2.5 px-4 font-semibold">Status</th>
                      <th className="py-2.5 px-4 font-semibold text-right">Total Rows</th>
                      <th className="py-2.5 px-4 font-semibold text-right">Valid Rows</th>
                      <th className="py-2.5 px-4 font-semibold text-right">Valuation</th>
                      <th className="py-2.5 px-4 font-semibold">Created Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-800">
                    {isLoadingBatches ? (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-slate-400">
                          <Loader2 className="w-5 h-5 animate-spin mx-auto text-blue-600 mb-2" />
                          Loading historical batches...
                        </td>
                      </tr>
                    ) : filteredBatches.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-slate-400">
                          No initial stock import batches found.
                        </td>
                      </tr>
                    ) : (
                      filteredBatches.map((b) => {
                        const totalVal = (b.staged_data as any)?.total_value
                        return (
                          <tr key={b.id} className="hover:bg-slate-50/50">
                            <td className="py-2.5 px-4 font-mono font-medium text-blue-700">{b.batch_number}</td>
                            <td className="py-2.5 px-4 text-slate-700">{b.file_name}</td>
                            <td className="py-2.5 px-4">
                              <span className={`inline-flex px-2 py-0.5 rounded text-[11px] font-semibold ${
                                b.status === 'COMPLETED'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : b.status === 'VALIDATED'
                                  ? 'bg-blue-100 text-blue-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}>
                                {b.status}
                              </span>
                            </td>
                            <td className="py-2.5 px-4 text-right font-medium">{b.total_rows}</td>
                            <td className="py-2.5 px-4 text-right font-semibold text-emerald-700">{b.valid_rows}</td>
                            <td className="py-2.5 px-4 text-right font-medium text-violet-700">
                              {totalVal ? `ETB ${parseFloat(String(totalVal)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
                            </td>
                            <td className="py-2.5 px-4 text-slate-500">
                              {b.created_at ? new Date(b.created_at).toLocaleDateString() : '—'}
                            </td>
                          </tr>
                        )
                      })
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="overflow-x-auto border border-slate-100 rounded-lg">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[11px] border-b border-slate-200">
                      <th className="py-2.5 px-4 font-semibold">Transaction Number</th>
                      <th className="py-2.5 px-4 font-semibold">Type</th>
                      <th className="py-2.5 px-4 font-semibold">Status</th>
                      <th className="py-2.5 px-4 font-semibold">Date</th>
                      <th className="py-2.5 px-4 font-semibold text-right">Lines</th>
                      <th className="py-2.5 px-4 font-semibold">Remarks</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-800">
                    {isLoadingTransactions ? (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-slate-400">
                          <Loader2 className="w-5 h-5 animate-spin mx-auto text-blue-600 mb-2" />
                          Loading opening balance vouchers...
                        </td>
                      </tr>
                    ) : filteredTransactions.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-slate-400">
                          No posted Opening Balance vouchers found.
                        </td>
                      </tr>
                    ) : (
                      filteredTransactions.map((tx) => (
                        <tr key={tx.id} className="hover:bg-slate-50/50">
                          <td className="py-2.5 px-4 font-mono font-medium text-blue-700">{tx.transaction_number}</td>
                          <td className="py-2.5 px-4">
                            <span className="font-semibold text-slate-700">{tx.transaction_type}</span>
                            <span className="text-[10px] text-slate-500 block">Opening Balance</span>
                          </td>
                          <td className="py-2.5 px-4">
                            <span className="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800">
                              {tx.status}
                            </span>
                          </td>
                          <td className="py-2.5 px-4 text-slate-600">{tx.transaction_date}</td>
                          <td className="py-2.5 px-4 text-right font-semibold text-slate-800">
                            {tx.lines?.length || 0}
                          </td>
                          <td className="py-2.5 px-4 text-slate-600 truncate max-w-xs">{tx.remarks || '—'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default OpeningBalancePage
