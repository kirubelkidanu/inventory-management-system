import React from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, ArrowRight, PlusCircle, LayoutList, Layers } from 'lucide-react'
import type { Transaction } from '@/types'

interface VoucherSuccessCardProps {
  transaction: Transaction
  title: string
  onReset: () => void
}

export const VoucherSuccessCard: React.FC<VoucherSuccessCardProps> = ({
  transaction,
  title,
  onReset,
}) => {
  return (
    <div className="mx-auto max-w-2xl rounded-2xl border border-emerald-200 bg-white p-8 shadow-lg">
      <div className="flex flex-col items-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 mb-4 animate-in fade-in zoom-in-75">
          <CheckCircle2 className="h-10 w-10" />
        </div>

        <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-700 border border-emerald-200 mb-2">
          {transaction.status || 'POSTED'} ATOMICALLY
        </span>

        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          {title} Successfully Posted
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Inventory balances and immutable stock movement ledger have been updated in a single atomic database transaction.
        </p>

        {/* Voucher summary box */}
        <div className="mt-6 w-full rounded-xl border border-slate-200 bg-slate-50/80 p-5 text-left">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <span className="text-xs font-medium text-slate-400">Voucher Number</span>
              <p className="font-mono text-base font-bold text-slate-900">
                {transaction.transaction_number}
              </p>
            </div>
            <div>
              <span className="text-xs font-medium text-slate-400">Transaction Date</span>
              <p className="text-sm font-semibold text-slate-800">
                {transaction.transaction_date}
              </p>
            </div>
            <div>
              <span className="text-xs font-medium text-slate-400">Voucher Type</span>
              <p className="text-sm font-semibold text-slate-800">
                {transaction.transaction_type}
              </p>
            </div>
            <div>
              <span className="text-xs font-medium text-slate-400">Items Count</span>
              <p className="text-sm font-semibold text-slate-800">
                {transaction.lines?.length || 0} line(s)
              </p>
            </div>
            {transaction.supplier_name && (
              <div className="sm:col-span-2">
                <span className="text-xs font-medium text-slate-400">Supplier</span>
                <p className="text-sm font-semibold text-slate-800">{transaction.supplier_name}</p>
              </div>
            )}
            {transaction.invoice_no && (
              <div>
                <span className="text-xs font-medium text-slate-400">Invoice No</span>
                <p className="text-sm font-mono text-slate-800">{transaction.invoice_no}</p>
              </div>
            )}
            {transaction.plate_no && (
              <div>
                <span className="text-xs font-medium text-slate-400">Transport Plate / Driver</span>
                <p className="text-sm text-slate-800">
                  {transaction.plate_no} {transaction.driver_name ? `(${transaction.driver_name})` : ''}
                </p>
              </div>
            )}
            {transaction.adjustment_reason && (
              <div className="sm:col-span-2">
                <span className="text-xs font-medium text-slate-400">Adjustment Reason</span>
                <p className="text-sm text-slate-800">{transaction.adjustment_reason}</p>
              </div>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition-colors"
          >
            <PlusCircle className="h-4 w-4 text-slate-500" />
            <span>Create Another Voucher</span>
          </button>

          <Link
            to="/transactions"
            className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-slate-800 transition-colors"
          >
            <LayoutList className="h-4 w-4 text-slate-400" />
            <span>View in Transaction Ledger</span>
            <ArrowRight className="h-4 w-4" />
          </Link>

          <Link
            to="/inventory"
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-200 transition-colors"
          >
            <Layers className="h-4 w-4 text-slate-500" />
            <span>Stock Balances</span>
          </Link>
        </div>
      </div>
    </div>
  )
}
