import React, { useState, useMemo } from 'react'
import {
  Briefcase,
  Plus,
  Search,
  Edit2,
  Power,
  AlertCircle,
  X,
  Loader2,
  MapPin,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { extractErrorMessage } from '@/features/transactions/useTransactionData'
import {
  useProjectsList,
  useCreateProject,
  useUpdateProject,
  type ProjectPayload,
} from './useSitesData'
import type { Project } from '@/types'
import { cn } from '@/lib/utils'

export const ProjectsPage: React.FC = () => {
  const { hasRole } = useAuth()
  const isAuthorized = hasRole('ADMIN', 'INVENTORY_MANAGER')

  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'INACTIVE'>('ALL')

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingProject, setEditingProject] = useState<Project | null>(null)
  const [formCode, setFormCode] = useState('')
  const [formName, setFormName] = useState('')
  const [formLocation, setFormLocation] = useState('')
  const [formIsActive, setFormIsActive] = useState(true)
  const [formError, setFormError] = useState<string | null>(null)

  const { data: projects = [], isLoading, error } = useProjectsList()

  const createMutation = useCreateProject()
  const updateMutation = useUpdateProject()

  // Filtered projects
  const filteredProjects = useMemo(() => {
    return projects.filter((prj) => {
      if (statusFilter === 'ACTIVE' && !prj.is_active) return false
      if (statusFilter === 'INACTIVE' && prj.is_active) return false

      if (!searchQuery.trim()) return true
      const q = searchQuery.toLowerCase().trim()
      return (
        prj.code.toLowerCase().includes(q) ||
        prj.name.toLowerCase().includes(q) ||
        (prj.location && prj.location.toLowerCase().includes(q))
      )
    })
  }, [projects, searchQuery, statusFilter])

  const openCreateModal = () => {
    setEditingProject(null)
    setFormCode('')
    setFormName('')
    setFormLocation('')
    setFormIsActive(true)
    setFormError(null)
    setIsModalOpen(true)
  }

  const openEditModal = (prj: Project) => {
    setEditingProject(prj)
    setFormCode(prj.code)
    setFormName(prj.name)
    setFormLocation(prj.location || '')
    setFormIsActive(prj.is_active)
    setFormError(null)
    setIsModalOpen(true)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    if (!formCode.trim()) {
      setFormError('Project code is required.')
      return
    }
    if (!formName.trim()) {
      setFormError('Project name is required.')
      return
    }

    const payload: ProjectPayload = {
      code: formCode.trim().toUpperCase(),
      name: formName.trim(),
      location: formLocation.trim() || null,
      is_active: formIsActive,
    }

    try {
      if (editingProject) {
        await updateMutation.mutateAsync({ id: editingProject.id, payload })
      } else {
        await createMutation.mutateAsync(payload)
      }
      setIsModalOpen(false)
    } catch (err: any) {
      setFormError(extractErrorMessage(err))
    }
  }

  const handleToggleActive = async (prj: Project) => {
    if (!isAuthorized) return
    const action = prj.is_active ? 'deactivate' : 'activate'
    if (confirm(`Are you sure you want to ${action} project '${prj.name}' (${prj.code})?`)) {
      try {
        await updateMutation.mutateAsync({
          id: prj.id,
          payload: { is_active: !prj.is_active },
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
            <Briefcase className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Project Sites
            </h1>
            <p className="text-xs text-slate-500">
              Manage client construction sites, projects, and geographic operations.
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
            <span>Add Project Site</span>
          </button>
        )}
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-rose-900">Error Loading Projects</h4>
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
            placeholder="Search by code, name, or location..."
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
            <option value="ALL">All ({projects.length})</option>
            <option value="ACTIVE">Active ({projects.filter((p) => p.is_active).length})</option>
            <option value="INACTIVE">Archived ({projects.filter((p) => !p.is_active).length})</option>
          </select>
        </div>
      </div>

      {/* Projects Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-4 w-36">Project Code</th>
                <th className="py-3 px-4">Project Name</th>
                <th className="py-3 px-4 w-64">Site Location</th>
                <th className="py-3 px-4 w-28 text-center">Status</th>
                {isAuthorized && <th className="py-3 px-4 w-28 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-normal">
              {isLoading ? (
                <tr>
                  <td colSpan={isAuthorized ? 5 : 4} className="py-8 text-center text-slate-400">
                    <div className="flex items-center justify-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-sky-600" />
                      <span>Loading project sites...</span>
                    </div>
                  </td>
                </tr>
              ) : filteredProjects.length === 0 ? (
                <tr>
                  <td colSpan={isAuthorized ? 5 : 4} className="py-8 text-center text-slate-400">
                    No project sites found matching your filter.
                  </td>
                </tr>
              ) : (
                filteredProjects.map((prj) => (
                  <tr key={prj.id} className={cn('hover:bg-slate-50/80', !prj.is_active && 'bg-slate-50/40 text-slate-400')}>
                    <td className="py-3 px-4 font-mono font-bold text-sky-700">
                      {prj.code}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-900">
                      {prj.name}
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      <div className="flex items-center gap-1.5">
                        <MapPin className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                        <span className="truncate">{prj.location || '—'}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={cn(
                          'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold border',
                          prj.is_active
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-amber-50 text-amber-700 border-amber-200'
                        )}
                      >
                        {prj.is_active ? 'Active' : 'Archived'}
                      </span>
                    </td>
                    {isAuthorized && (
                      <td className="py-3 px-4 text-right space-x-1">
                        <button
                          type="button"
                          onClick={() => openEditModal(prj)}
                          className="p-1 rounded-md text-slate-500 hover:text-sky-600 hover:bg-sky-50 transition-colors"
                          title="Edit Project"
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleToggleActive(prj)}
                          className={cn(
                            'p-1 rounded-md transition-colors',
                            prj.is_active
                              ? 'text-slate-400 hover:text-amber-600 hover:bg-amber-50'
                              : 'text-slate-400 hover:text-emerald-600 hover:bg-emerald-50'
                          )}
                          title={prj.is_active ? 'Deactivate / Archive' : 'Reactivate'}
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
                  <Briefcase className="h-4 w-4" />
                </div>
                <h3 className="text-sm font-bold text-slate-900">
                  {editingProject ? 'Edit Project Site' : 'New Project Site'}
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
                  Project Code <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={formCode}
                  onChange={(e) => setFormCode(e.target.value.toUpperCase())}
                  placeholder="e.g. PRJ-AB or PRJ-KZ"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 font-mono font-semibold focus:outline-hidden focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Project Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Ambo Project"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Site Geographic Location
                </label>
                <input
                  type="text"
                  value={formLocation}
                  onChange={(e) => setFormLocation(e.target.value)}
                  placeholder="e.g. Ambo, Oromia"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:border-sky-500"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="project-active"
                  checked={formIsActive}
                  onChange={(e) => setFormIsActive(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                />
                <label htmlFor="project-active" className="text-xs font-medium text-slate-700">
                  Active (available for warehouse assignment and vouchers)
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
                  <span>{editingProject ? 'Update Project' : 'Create Project'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default ProjectsPage
