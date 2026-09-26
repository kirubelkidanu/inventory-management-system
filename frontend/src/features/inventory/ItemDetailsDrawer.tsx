import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  X,
  Warehouse,
  History,
  Info,
  ArrowDownToLine,
  ArrowUpFromLine,
  ShieldCheck,
  RotateCw,
} from 'lucide-react'
import type { Item } from '@/types'
import { useInventoryBalances, useItemStockMovements } from './useInventoryData'
import { cn } from '@/lib/utils'

interface ItemDetailsDrawerProps {
  item: Item | null
  onClose: () => void
  categoryName?: string
}

export const ItemDetailsDrawer: React.FC<ItemDetailsDrawerProps> = ({
  item,
  onClose,
  categoryName,
}) => {
  const [activeTab, setActiveTab] = useState<'balances' | 'movements'>('balances')

  const {
    data: balances,
    isLoading: balancesLoading,
    refetch: refetchBalances,
  } = useInventoryBalances({
    item_id: item?.id,
  })

  const {
    data: movements,
    isLoading: movementsLoading,
    refetch: refetchMovements,
  } = useItemStockMovements(item?.id)

  if (!item) return null

  // Calculate totals across warehouses
  const totalOnHand = (balances || []).reduce(
    (sum, b) => sum + Number(b.quantity_on_hand),
    0
  )
  const totalReserved = (balances || []).reduce(
    (sum, b) => sum + Number(b.quantity_reserved),
    0
  )
  const totalAvailable = totalOnHand - totalReserved

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
        <div className="w-screen max-w-2xl bg-white shadow-2xl flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-slate-50">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sky-100 text-sky-700 font-mono font-bold text-sm">
                SKU
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-slate-900 font-mono">
                    {item.item_code}
                  </h2>
                  <span
                    className={cn(
                      'rounded-full px-2 py-0.5 text-[10px] font-semibold border',
                      item.is_active
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-slate-100 text-slate-600 border-slate-200'
                    )}
                  >
                    {item.is_active ? 'Active SKU' : 'Archived'}
                  </span>
                </div>
                <p className="text-xs text-slate-500 truncate max-w-md">
                  {item.description}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Master Item Specifications Card */}
          <div className="border-b border-slate-200 bg-white p-6">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <span className="text-[10px] font-semibold text-slate-400 uppercase">Category</span>
                <p className="mt-0.5 text-xs font-semibold text-slate-800">
                  {categoryName || item.category?.name || 'General'}
                </p>
              </div>
              <div>
                <span className="text-[10px] font-semibold text-slate-400 uppercase">Default Unit</span>
                <p className="mt-0.5 text-xs font-mono font-semibold text-slate-800">
                  {item.default_unit}
                </p>
              </div>
              <div>
                <span className="text-[10px] font-semibold text-slate-400 uppercase">Global On-Hand</span>
                <p className="mt-0.5 text-xs font-mono font-bold text-slate-900">
                  {totalOnHand.toLocaleString()}
                </p>
              </div>
              <div>
                <span className="text-[10px] font-semibold text-slate-400 uppercase">Global Available</span>
                <p className="mt-0.5 text-xs font-mono font-bold text-emerald-600">
                  {totalAvailable.toLocaleString()}
                </p>
              </div>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex border-b border-slate-200 bg-slate-50 px-6">
            <button
              type="button"
              onClick={() => setActiveTab('balances')}
              className={cn(
                'flex items-center gap-2 border-b-2 py-3 px-3 text-xs font-semibold transition-colors',
                activeTab === 'balances'
                  ? 'border-sky-600 text-sky-600 bg-white'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              )}
            >
              <Warehouse className="h-4 w-4" />
              <span>Warehouse Stock Balances</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('movements')}
              className={cn(
                'flex items-center gap-2 border-b-2 py-3 px-3 text-xs font-semibold transition-colors',
                activeTab === 'movements'
                  ? 'border-sky-600 text-sky-600 bg-white'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              )}
            >
              <History className="h-4 w-4" />
              <span>Audit Stock Movements</span>
            </button>
          </div>

          {/* Drawer Content Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {activeTab === 'balances' ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <Info className="h-4 w-4 text-sky-600" />
                    <span>Authoritative projected balances per warehouse</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => refetchBalances()}
                    className="p-1 text-slate-400 hover:text-slate-600"
                    title="Refresh balances"
                  >
                    <RotateCw className={cn('h-3.5 w-3.5', balancesLoading && 'animate-spin')} />
                  </button>
                </div>

                <div className="overflow-hidden rounded-xl border border-slate-200">
                  <table className="min-w-full divide-y divide-slate-200 text-xs">
                    <thead className="bg-slate-50 font-semibold text-slate-500 uppercase">
                      <tr>
                        <th className="px-4 py-2.5 text-left">Warehouse</th>
                        <th className="px-4 py-2.5 text-right">On Hand</th>
                        <th className="px-4 py-2.5 text-right">Reserved</th>
                        <th className="px-4 py-2.5 text-right">Available</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {(balances || []).length === 0 ? (
                        <tr>
                          <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                            No inventory balance recorded in any warehouse yet.
                          </td>
                        </tr>
                      ) : (
                        (balances || []).map((b) => (
                          <tr key={b.warehouse_id} className="hover:bg-slate-50">
                            <td className="px-4 py-3 font-medium text-slate-900">
                              {b.warehouse_name}
                              <span className="block text-[10px] text-slate-400 font-mono">
                                {b.warehouse_code}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-right font-mono font-semibold text-slate-800">
                              {Number(b.quantity_on_hand).toLocaleString()} {b.unit}
                            </td>
                            <td className="px-4 py-3 text-right font-mono text-amber-600">
                              {Number(b.quantity_reserved).toLocaleString()} {b.unit}
                            </td>
                            <td className="px-4 py-3 text-right font-mono font-bold text-emerald-600">
                              {Number(b.available_quantity).toLocaleString()} {b.unit}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <ShieldCheck className="h-4 w-4 text-emerald-600" />
                    <span>Immutable append-only ledger entries</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => refetchMovements()}
                    className="p-1 text-slate-400 hover:text-slate-600"
                    title="Refresh movements"
                  >
                    <RotateCw className={cn('h-3.5 w-3.5', movementsLoading && 'animate-spin')} />
                  </button>
                </div>

                <div className="overflow-hidden rounded-xl border border-slate-200">
                  <table className="min-w-full divide-y divide-slate-200 text-xs">
                    <thead className="bg-slate-50 font-semibold text-slate-500 uppercase">
                      <tr>
                        <th className="px-3 py-2.5 text-left">Date</th>
                        <th className="px-3 py-2.5 text-left">Type</th>
                        <th className="px-3 py-2.5 text-right">Quantity</th>
                        <th className="px-3 py-2.5 text-right">Running Balance</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {(movements || []).length === 0 ? (
                        <tr>
                          <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                            No movements recorded for this item yet.
                          </td>
                        </tr>
                      ) : (
                        (movements || []).map((m) => (
                          <tr key={m.id} className="hover:bg-slate-50">
                            <td className="px-3 py-2.5 font-mono text-slate-600 text-[11px]">
                              {m.movement_date}
                            </td>
                            <td className="px-3 py-2.5">
                              <span
                                className={cn(
                                  'rounded-md px-1.5 py-0.5 text-[10px] font-bold',
                                  m.movement_type === 'IN'
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : 'bg-red-100 text-red-800'
                                )}
                              >
                                {m.movement_type}
                              </span>
                            </td>
                            <td className="px-3 py-2.5 text-right font-mono font-semibold">
                              {m.movement_type === 'IN' ? (
                                <span className="text-emerald-600">+{m.quantity}</span>
                              ) : (
                                <span className="text-red-600">-{m.quantity}</span>
                              )}
                            </td>
                            <td className="px-3 py-2.5 text-right font-mono font-bold text-sky-700">
                              {m.running_balance !== null && m.running_balance !== undefined
                                ? m.running_balance
                                : '—'}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Footer Voucher Actions */}
          <div className="border-t border-slate-200 bg-slate-50 p-4 flex items-center justify-between gap-3">
            <span className="text-xs text-slate-500">Fast Transactions:</span>
            <div className="flex gap-2">
              <Link
                to={`/transactions/grv?item_id=${item.id}`}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500"
              >
                <ArrowDownToLine className="h-3.5 w-3.5" />
                <span>Receive (GRV)</span>
              </Link>
              <Link
                to={`/transactions/siv?item_id=${item.id}`}
                className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-500"
              >
                <ArrowUpFromLine className="h-3.5 w-3.5" />
                <span>Issue (SIV)</span>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ItemDetailsDrawer
