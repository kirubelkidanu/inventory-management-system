import React from 'react'
import { Link } from 'react-router-dom'
import { useDashboardData } from './useDashboardData'
import {
  PackageCheck,
  Warehouse,
  Truck,
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  PackageOpen,
  Undo2,
  Sliders,
  CheckCircle2,
  Clock,
  RotateCw,
  Scale,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export const DashboardPage: React.FC = () => {
  const {
    metrics,
    inTransitItems,
    recentMovements,
    isLoading,
    refetchAll,
  } = useDashboardData()

  const displayMovements = recentMovements
  const displayInTransit = inTransitItems

  const getTypeBadgeStyle = (type: string) => {
    switch (type) {
      case 'GRV':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200'
      case 'SIV':
        return 'bg-sky-50 text-sky-700 border-sky-200'
      case 'ISTV':
        return 'bg-purple-50 text-purple-700 border-purple-200'
      case 'ISTRV':
        return 'bg-teal-50 text-teal-700 border-teal-200'
      case 'SRV':
        return 'bg-rose-50 text-rose-700 border-rose-200'
      default:
        return 'bg-amber-50 text-amber-700 border-amber-200'
    }
  }

  return (
    <div className="space-y-8">
      {/* Top Header with Refresh */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Executive Operations Dashboard
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Live inventory velocity, dual-write ledger health, and in-transit tracking.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetchAll()}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50"
        >
          <RotateCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
          <span>Sync Real-Time Metrics</span>
        </button>
      </div>

      {/* Summary KPI Metric Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {/* 1. Total Catalog Items */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-shadow hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
              Registered SKUs
            </span>
            <div className="rounded-lg border border-sky-100 bg-sky-50 p-2 text-sky-600">
              <PackageCheck className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold text-slate-900">
              {metrics.totalCatalogItems.toLocaleString()}
            </span>
            <p className="mt-1 text-xs text-slate-500">Master Item Catalog</p>
          </div>
        </div>

        {/* 2. Active Warehouses & Projects */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-shadow hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
              Operating Stores
            </span>
            <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-2 text-emerald-600">
              <Warehouse className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold text-slate-900">
              {metrics.activeWarehousesCount}
            </span>
            <p className="mt-1 text-xs text-slate-500">
              {metrics.activeProjectsCount} Associated Active Projects
            </p>
          </div>
        </div>

        {/* 3. In-Transit Transfer Batches */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-shadow hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
              In-Transit Batches
            </span>
            <div
              className={cn(
                'rounded-lg border p-2',
                metrics.inTransitBatchesCount > 0
                  ? 'border-amber-200 bg-amber-50 text-amber-600'
                  : 'border-slate-200 bg-slate-50 text-slate-400'
              )}
            >
              <Truck className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-slate-900">
                {metrics.inTransitBatchesCount}
              </span>
              {metrics.inTransitBatchesCount > 0 && (
                <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
                  En-Route
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-slate-500">Awaiting ISTRV Destination Receipt</p>
          </div>
        </div>

        {/* 4. Reconciliation Discrepancy Status */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-shadow hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
              Ledger Health
            </span>
            <div
              className={cn(
                'rounded-lg border p-2',
                metrics.hasDiscrepancies
                  ? 'border-red-200 bg-red-50 text-red-600'
                  : 'border-emerald-200 bg-emerald-50 text-emerald-600'
              )}
            >
              {metrics.hasDiscrepancies ? (
                <AlertTriangle className="h-5 w-5" />
              ) : (
                <CheckCircle2 className="h-5 w-5" />
              )}
            </div>
          </div>
          <div className="mt-4">
            {metrics.hasDiscrepancies ? (
              <div>
                <span className="text-3xl font-extrabold text-red-600">
                  {metrics.reconciliationDiscrepanciesCount}
                </span>
                <p className="mt-1 text-xs font-medium text-red-600">Discrepancies Detected</p>
              </div>
            ) : (
              <div>
                <span className="text-3xl font-extrabold text-emerald-600">Balanced</span>
                <p className="mt-1 text-xs text-slate-500">Zero Dual-Write Drift</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Action Launchpad */}
      <div>
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">Immediate Voucher Launchpad</h2>
          <span className="text-xs text-slate-500">Direct transaction entry</span>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Link
            to="/transactions/grv"
            className="group flex flex-col items-center rounded-xl border border-slate-200 bg-white p-4 text-center shadow-xs transition hover:border-emerald-300 hover:shadow-md"
          >
            <div className="rounded-lg bg-emerald-50 p-2.5 text-emerald-600 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
              <ArrowDownToLine className="h-5 w-5" />
            </div>
            <span className="mt-2.5 text-xs font-semibold text-slate-900">Receive (GRV)</span>
            <span className="text-[10px] text-slate-500">Vendor receipt</span>
          </Link>

          <Link
            to="/transactions/siv"
            className="group flex flex-col items-center rounded-xl border border-slate-200 bg-white p-4 text-center shadow-xs transition hover:border-sky-300 hover:shadow-md"
          >
            <div className="rounded-lg bg-sky-50 p-2.5 text-sky-600 group-hover:bg-sky-600 group-hover:text-white transition-colors">
              <ArrowUpFromLine className="h-5 w-5" />
            </div>
            <span className="mt-2.5 text-xs font-semibold text-slate-900">Issue (SIV)</span>
            <span className="text-[10px] text-slate-500">Project requisition</span>
          </Link>

          <Link
            to="/transactions/istv"
            className="group flex flex-col items-center rounded-xl border border-slate-200 bg-white p-4 text-center shadow-xs transition hover:border-purple-300 hover:shadow-md"
          >
            <div className="rounded-lg bg-purple-50 p-2.5 text-purple-600 group-hover:bg-purple-600 group-hover:text-white transition-colors">
              <Truck className="h-5 w-5" />
            </div>
            <span className="mt-2.5 text-xs font-semibold text-slate-900">Dispatch (ISTV)</span>
            <span className="text-[10px] text-slate-500">Store transfer out</span>
          </Link>

          <Link
            to="/transactions/istrv"
            className="group flex flex-col items-center rounded-xl border border-slate-200 bg-white p-4 text-center shadow-xs transition hover:border-teal-300 hover:shadow-md"
          >
            <div className="rounded-lg bg-teal-50 p-2.5 text-teal-600 group-hover:bg-teal-600 group-hover:text-white transition-colors">
              <PackageOpen className="h-5 w-5" />
            </div>
            <span className="mt-2.5 text-xs font-semibold text-slate-900">Receive (ISTRV)</span>
            <span className="text-[10px] text-slate-500">Confirm in-transit</span>
          </Link>

          <Link
            to="/transactions/srv"
            className="group flex flex-col items-center rounded-xl border border-slate-200 bg-white p-4 text-center shadow-xs transition hover:border-rose-300 hover:shadow-md"
          >
            <div className="rounded-lg bg-rose-50 p-2.5 text-rose-600 group-hover:bg-rose-600 group-hover:text-white transition-colors">
              <Undo2 className="h-5 w-5" />
            </div>
            <span className="mt-2.5 text-xs font-semibold text-slate-900">Return (SRV)</span>
            <span className="text-[10px] text-slate-500">Store return voucher</span>
          </Link>

          <Link
            to="/transactions/adjustment"
            className="group flex flex-col items-center rounded-xl border border-slate-200 bg-white p-4 text-center shadow-xs transition hover:border-amber-300 hover:shadow-md"
          >
            <div className="rounded-lg bg-amber-50 p-2.5 text-amber-600 group-hover:bg-amber-600 group-hover:text-white transition-colors">
              <Sliders className="h-5 w-5" />
            </div>
            <span className="mt-2.5 text-xs font-semibold text-slate-900">Stock Adjustment</span>
            <span className="text-[10px] text-slate-500">Controlled correction</span>
          </Link>
        </div>
      </div>

      {/* In-Transit Attention Widget */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-amber-50 p-2 text-amber-600">
              <Truck className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                In-Transit Transfer Attention
              </h3>
              <p className="text-xs text-slate-500">
                Dispatches en-route awaiting physical inspection and ISTRV receipt confirmation
              </p>
            </div>
          </div>
          <Link
            to="/reports/in-transit"
            className="inline-flex items-center gap-1 text-xs font-semibold text-sky-600 hover:text-sky-700"
          >
            <span>View Full Report</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {displayInTransit.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500">
            No inventory items currently in transit across warehouses.
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 font-semibold text-slate-500 uppercase">
                <tr>
                  <th scope="col" className="px-4 py-2.5">ISTV Number</th>
                  <th scope="col" className="px-4 py-2.5">Logistics Route</th>
                  <th scope="col" className="px-4 py-2.5">Vehicle & Driver</th>
                  <th scope="col" className="px-4 py-2.5">Item SKU</th>
                  <th scope="col" className="px-4 py-2.5 text-right">In-Transit Qty</th>
                  <th scope="col" className="px-4 py-2.5">Status</th>
                  <th scope="col" className="px-4 py-2.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {displayInTransit.map((tr) => (
                  <tr key={tr.transfer_record_id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3 font-mono font-semibold text-slate-900">
                      {tr.istv_number}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      <span className="font-medium">{tr.source_warehouse_code}</span> &rarr;{' '}
                      <span className="font-medium">{tr.destination_warehouse_code}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      <p className="font-medium text-slate-800">{tr.plate_no || 'Pending Plate'}</p>
                      <p className="text-[11px] text-slate-500">{tr.driver_name || 'Driver unassigned'}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono font-medium text-slate-900">{tr.item_code}</span>
                      <p className="text-[11px] text-slate-500 truncate max-w-[200px]">
                        {tr.item_description}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-amber-600">
                      {tr.remaining_quantity} {tr.unit}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 border border-amber-200">
                        <Clock className="h-3 w-3" />
                        In Transit
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to="/transactions/istrv"
                        className="inline-flex items-center gap-1 rounded-md bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-700 hover:bg-teal-100"
                      >
                        Receive &rarr;
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recent Inventory Activity Widget */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-sky-50 p-2 text-sky-600">
              <Scale className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Recent Physical Stock Movements
              </h3>
              <p className="text-xs text-slate-500">
                Chronological ledger activity recorded through the atomic TransactionService
              </p>
            </div>
          </div>
          <Link
            to="/reports/trial-balance"
            className="inline-flex items-center gap-1 text-xs font-semibold text-sky-600 hover:text-sky-700"
          >
            <span>Full Trial Balance</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {displayMovements.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500">
            No stock movements recorded yet.
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 font-semibold text-slate-500 uppercase">
                <tr>
                  <th scope="col" className="px-4 py-2.5">Date</th>
                  <th scope="col" className="px-4 py-2.5">Voucher #</th>
                  <th scope="col" className="px-4 py-2.5">Type</th>
                  <th scope="col" className="px-4 py-2.5">Reference</th>
                  <th scope="col" className="px-4 py-2.5">Warehouse</th>
                  <th scope="col" className="px-4 py-2.5">SKU Item</th>
                  <th scope="col" className="px-4 py-2.5 text-right">Qty</th>
                  <th scope="col" className="px-4 py-2.5 text-right">Running Balance</th>
                  <th scope="col" className="px-4 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {displayMovements.map((m) => (
                  <tr key={m.movement_id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3 font-mono text-slate-600">{m.movement_date}</td>
                    <td className="px-4 py-3 font-mono font-semibold text-slate-900">
                      {m.transaction_number}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'inline-flex rounded-md border px-2 py-0.5 text-[11px] font-semibold',
                          getTypeBadgeStyle(m.transaction_type)
                        )}
                      >
                        {m.transaction_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-700">{m.reference_number || '—'}</td>
                    <td className="px-4 py-3 text-slate-700">{m.warehouse_name}</td>
                    <td className="px-4 py-3">
                      <p className="font-mono font-medium text-slate-900">{m.item_code}</p>
                      <p className="text-[11px] text-slate-500 truncate max-w-[200px]">
                        {m.item_description}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold">
                      {m.signed_quantity.toString().startsWith('-') ? (
                        <span className="text-red-600">{m.signed_quantity}</span>
                      ) : (
                        <span className="text-emerald-600">{m.signed_quantity}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-sky-700">
                      {m.running_balance || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 border border-emerald-200">
                        <ShieldCheck className="h-3 w-3" />
                        {m.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default DashboardPage
