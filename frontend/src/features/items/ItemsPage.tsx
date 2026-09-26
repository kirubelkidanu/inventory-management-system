import React, { useState } from 'react'
import { Search, Plus, CheckCircle, XCircle } from 'lucide-react'

export const ItemsPage: React.FC = () => {
  const [search, setSearch] = useState('')

  const dummyItems = [
    {
      id: '1',
      item_code: 'ITM-CONC-001',
      description: 'Portland Cement Grade 42.5N',
      category: 'Raw Materials',
      default_unit: 'BAG',
      is_active: true,
    },
    {
      id: '2',
      item_code: 'ITM-STEEL-012',
      description: 'Rebar Steel 12mm High Yield',
      category: 'Metals',
      default_unit: 'TON',
      is_active: true,
    },
    {
      id: '3',
      item_code: 'ITM-TIMBER-004',
      description: 'Construction Timber 2x4x12',
      category: 'Timber',
      default_unit: 'PCS',
      is_active: true,
    },
    {
      id: '4',
      item_code: 'ITM-PAINT-022',
      description: 'Exterior Weatherproof Emulsion White',
      category: 'Finishing',
      default_unit: 'LTR',
      is_active: false,
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Item Master Catalog</h1>
          <p className="mt-1 text-sm text-slate-500">
            Authoritative master item repository, unit specifications, and category classifications.
          </p>
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-sky-500"
        >
          <Plus className="h-4 w-4" />
          <span>Register New SKU</span>
        </button>
      </div>

      {/* Search Bar */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="relative">
          <Search className="pointer-events-none absolute inset-y-0 left-0 my-auto ml-3 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search SKU code, description, or category..."
            className="block w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm placeholder-slate-400 focus:border-sky-500 focus:outline-hidden"
          />
        </div>
      </div>

      {/* Catalog Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold text-slate-500 uppercase">
              <tr>
                <th scope="col" className="px-6 py-3.5">SKU Code</th>
                <th scope="col" className="px-6 py-3.5">Item Description</th>
                <th scope="col" className="px-6 py-3.5">Category</th>
                <th scope="col" className="px-6 py-3.5">Default Unit</th>
                <th scope="col" className="px-6 py-3.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {dummyItems.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/70">
                  <td className="px-6 py-4 font-mono font-medium text-slate-900">{item.item_code}</td>
                  <td className="px-6 py-4 text-slate-700">{item.description}</td>
                  <td className="px-6 py-4 text-slate-500">{item.category}</td>
                  <td className="px-6 py-4 font-mono text-xs text-slate-600">{item.default_unit}</td>
                  <td className="px-6 py-4">
                    {item.is_active ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-200">
                        <CheckCircle className="h-3 w-3" />
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 border border-slate-200">
                        <XCircle className="h-3 w-3" />
                        Archived
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default ItemsPage
