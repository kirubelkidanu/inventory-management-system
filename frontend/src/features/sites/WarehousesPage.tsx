import React, { useState, useMemo } from 'react'
import {
  Warehouse as WarehouseIcon,
  Plus,
  Search,
  Edit2,
  Power,
  AlertCircle,
  X,
  Loader2,
  Building2,
  MapPin,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { extractErrorMessage } from '@/features/transactions/useTransactionData'
import {
  useWarehousesList,
  useProjectsList,
  useCreateWarehouse,
  useUpdateWarehouse,
  type WarehousePayload,
} from './useSitesData'
import type { Warehouse } from '@/types'
import { cn } from '@/lib/utils'

export const WarehousesPage: React.FC = () => {
  const { hasRole } = useAuth()
  const isAuthorized = hasRole('ADMIN', 'INVENTORY_MANAGER')

  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'INACTIVE'>('ALL')

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingWarehouse, setEditingWarehouse] = useState<Warehouse | null>(null)
  const [formCode, setFormCode] = useState('')
  const [formName, setFormName] = useState('')
  const [formLocation, setFormLocation] = useState('')
  const [formProjectId, setFormProjectId] = useState<string>('')
  const [formIsActive, setFormIsActive] = useState(true)
  const [formError, setFormError] = useState<string | null>(null)

  const { data: warehouses = [], isLoading, error } = useWarehousesList()
  const { data: projects = [] } = useProjectsList()

  const createMutation = useCreateWarehouse()
  const updateMutation = useUpdateWarehouse()

  // Project lookup map
  const projectMap = useMemo(() => {
    const map = new Map<string, string>()
    projects.forEach((p) => {
      map.set(p.id, `${p.name} (${p.code})`)
    })
    return map
  }, [projects])

  // Filtered warehouses
  const filteredWarehouses = useMemo(() => {
    return warehouses.filter((wh) => {
      if (statusFilter === 'ACTIVE' && !wh.is_active) return false
      if (statusFilter === 'INACTIVE' && wh.is_active) return false

      if (!searchQuery.trim()) return true
      const q = searchQuery.toLowerCase().trim()
      const projectName = wh.default_project_id ? (projectMap.get(wh.default_project_id) || '') : ''
      return (
        wh.code.toLowerCase().includes(q) ||
        wh.name.toLowerCase().includes(q) ||
        (wh.location && wh.location.toLowerCase().includes(q)) ||
        projectName.toLowerCase().includes(q)
      )
    })
  }, [warehouses, searchQuery, statusFilter, projectMap])

  const openCreateModal = () => {
    setEditingWarehouse(null)
    setFormCode('')
    setFormName('')
    setFormLocation('')
    setFormProjectId(projects[0]?.id || '')
    setFormIsActive(true)
    setFormError(null)
    setIsModalOpen(true)
  }

  const openEditModal = (wh: Warehouse) => {
    setEditingWarehouse(wh)
    setFormCode(wh.code)
    setFormName(wh.name)
    setFormLocation(wh.location || '')
    setFormProjectId(wh.default_project_id || '')
    setFormIsActive(wh.is_active)
    setFormError(null)
    setIsModalOpen(true)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    if (!formCode.trim()) {
      setFormError('Warehouse code is required.')
      return
    }
    if (!formName.trim()) {
      setFormError('Warehouse name is required.')
      return
    }

    const payload: WarehousePayload = {
      code: formCode.trim().toUpperCase(),
      name: formName.trim(),
      location: formLocation.trim() || null,
      default_project_id: formProjectId || null,
      is_active: formIsActive,
    }

    try {
      if (editingWarehouse) {
        await updateMutation.mutateAsync({ id: editingWarehouse.id, payload })
      } else {
        await createMutation.mutateAsync(payload)
      }
      setIsModalOpen(false)
    } catch (err: any) {
      setFormError(extractErrorMessage(err))
    }
  }

  const handleToggleActive = async (wh: Warehouse) => {
    if (!isAuthorized) return
    const action = wh.is_active ? 'deactivate' : 'activate'
    if (confirm(`Are you sure you want to ${action} warehouse '${wh.name}' (${wh.code})?`)) {
      try {
        await updateMutation.mutateAsync({
          id: wh.id,
          payload: { is_active: !wh.is_active },
        })
      } catch (err: any) {
        alert(extractErrorMessage(err))
      }
    }
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-sky-100 text-sky-700 shadow-xs">
            <WarehouseIcon className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Warehouse Bin Locations
            </h1>
            <p className="text-xs text-slate-500">
              Manage client store locations, warehouse bin codes, and associate them with project sites.
            </p>
          </div>
        </div>

        {isAuthorized && (
          <button
            type="button"
            onClick={openCreateModal}
            className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-sky-500 transition-colors"
          >
            <Plus className="h-4 w-4" />
            <span>Add Warehouse / Bin</span>
          </button>
        )}
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-rose-900">Error Loading Warehouses</h4>
            <p className="text-xs text-rose-700 mt-0.5">{extractErrorMessage(error)}</p>
          </div>
        </div>
      )}

      {/* Filters Card */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
        <div className="relative flex-1 w-full sm:max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by code, name, location, or project..."
            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:border-sky-500"
          />
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className="text-xs font-medium text-slate-500">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="text-xs rounded-lg border border-slate-300 px-3 py-1.5 bg-white text-slate-700"
          >
            <option value="ALL">All ({warehouses.length})</option>
            <option value="ACTIVE">Active ({warehouses.filter((w) => w.is_active).length})</option>
            <option value="INACTIVE">Archived ({warehouses.filter((w) => !w.is_active).length})</option>
          </select>
        </div>
      </div>

      {/* Warehouses Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-4 w-36">Bin Code</th>
                <th className="py-3 px-4">Warehouse Name</th>
                <th className="py-3 px-4 w-48">Site Location</th>
                <th className="py-3 px-4 w-56">Associated Project</th>
                <th className="py-3 px-4 w-28 text-center">Status</th>
                {isAuthorized && <th className="py-3 px-4 w-28 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-normal">
              {isLoading ? (
                <tr>
                  <td colSpan={isAuthorized ? 6 : 5} className="py-8 text-center text-slate-400">
                    <div className="flex items-center justify-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-sky-600" />
                      <span>Loading warehouse bins...</span>
                    </div>
                  </td>
                </tr>
              ) : filteredWarehouses.length === 0 ? (
                <tr>
                  <td colSpan={isAuthorized ? 6 : 5} className="py-8 text-center text-slate-400">
                    No warehouse bin locations found matching your filter.
                  </td>
                </tr>
              ) : (
                filteredWarehouses.map((wh) => (
                  <tr key={wh.id} className={cn('hover:bg-slate-50/80', !wh.is_active && 'bg-slate-50/40 text-slate-400')}>
                    <td className="py-3 px-4 font-mono font-bold text-sky-700">
                      {wh.code}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-900">
                      {wh.name}
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      <div className="flex items-center gap-1.5">
                        <MapPin className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                        <span className="truncate">{wh.location || '—'}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-slate-700 font-medium">
                      {wh.default_project_id ? (
                        <div className="flex items-center gap-1.5">
                          <Building2 className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                          <span className="truncate">{projectMap.get(wh.default_project_id) || 'Assigned'}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">None</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={cn(
                          'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold border',
                          wh.is_active
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-amber-50 text-amber-700 border-amber-200'
                        )}
                      >
                        {wh.is_active ? 'Active' : 'Archived'}
                      </span>
                    </td>
                    {isAuthorized && (
                      <td className="py-3 px-4 text-right space-x-1">
                        <button
                          type="button"
                          onClick={() => openEditModal(wh)}
                          className="p-1 rounded-md text-slate-500 hover:text-sky-600 hover:bg-sky-50 transition-colors"
                          title="Edit Warehouse"
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleToggleActive(wh)}
                          className={cn(
                            'p-1 rounded-md transition-colors',
                            wh.is_active
                              ? 'text-slate-400 hover:text-amber-600 hover:bg-amber-50'
                              : 'text-slate-400 hover:text-emerald-600 hover:bg-emerald-50'
                          )}
                          title={wh.is_active ? 'Deactivate / Archive' : 'Reactivate'}
                        >
                          <Power className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create / Edit Modal Dialog */}
      {isModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs"
        >
          <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-100 text-sky-700">
                  <WarehouseIcon className="h-4 w-4" />
                </div>
                <h3 className="text-sm font-bold text-slate-900">
                  {editingWarehouse ? 'Edit Warehouse Bin Location' : 'New Warehouse Bin Location'}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleSave} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{formError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Warehouse Code <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={formCode}
                  onChange={(e) => setFormCode(e.target.value.toUpperCase())}
                  placeholder="e.g. KZ-WH-001 or AB-WH-0001"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 font-mono font-semibold focus:outline-hidden focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Warehouse / Bin Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Kazanchis Store / Bin 001"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Physical Site Location
                </label>
                <input
                  type="text"
                  value={formLocation}
                  onChange={(e) => setFormLocation(e.target.value)}
                  placeholder="e.g. Kazanchis Site, Addis Ababa"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Associated Project Site
                </label>
                <select
                  value={formProjectId}
                  onChange={(e) => setFormProjectId(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white text-slate-700 focus:outline-hidden focus:border-sky-500"
                >
                  <option value="">No Project Assigned</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="warehouse-active"
                  checked={formIsActive}
                  onChange={(e) => setFormIsActive(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                />
                <label htmlFor="warehouse-active" className="text-xs font-medium text-slate-700">
                  Active (available in transaction dropdowns and vouchers)
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-sky-500 disabled:opacity-50"
                >
                  {(createMutation.isPending || updateMutation.isPending) && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  )}
                  <span>{editingWarehouse ? 'Update Bin' : 'Create Bin'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default WarehousesPage
