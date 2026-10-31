import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Warehouse, Project } from '@/types'

export interface WarehousePayload {
  code: string
  name: string
  location?: string | null
  default_project_id?: string | null
  is_active: boolean
}

export interface ProjectPayload {
  code: string
  name: string
  location?: string | null
  is_active: boolean
}

// ---------------------------------------------------------------------------
// Warehouse Hooks
// ---------------------------------------------------------------------------

export function useWarehousesList(params?: { is_active?: boolean }) {
  return useQuery<Warehouse[]>({
    queryKey: ['warehouses', params],
    queryFn: async () => {
      const queryParams: Record<string, any> = {}
      if (params?.is_active !== undefined) {
        queryParams.is_active = params.is_active
      }
      const response = await api.get<Warehouse[]>('/warehouses', { params: queryParams })
      return response.data || []
    },
    staleTime: 30 * 1000,
  })
}

export function useCreateWarehouse() {
  const queryClient = useQueryClient()
  return useMutation<Warehouse, Error, WarehousePayload>({
    mutationFn: async (payload) => {
      const response = await api.post<Warehouse>('/warehouses', payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] })
    },
  })
}

export function useUpdateWarehouse() {
  const queryClient = useQueryClient()
  return useMutation<Warehouse, Error, { id: string; payload: Partial<WarehousePayload> }>({
    mutationFn: async ({ id, payload }) => {
      const response = await api.put<Warehouse>(`/warehouses/${id}`, payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] })
    },
  })
}

export function useDeleteWarehouse() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await api.delete(`/warehouses/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Project Hooks
// ---------------------------------------------------------------------------

export function useProjectsList(params?: { is_active?: boolean }) {
  return useQuery<Project[]>({
    queryKey: ['projects', params],
    queryFn: async () => {
      const queryParams: Record<string, any> = {}
      if (params?.is_active !== undefined) {
        queryParams.is_active = params.is_active
      }
      const response = await api.get<Project[]>('/projects', { params: queryParams })
      return response.data || []
    },
    staleTime: 30 * 1000,
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation<Project, Error, ProjectPayload>({
    mutationFn: async (payload) => {
      const response = await api.post<Project>('/projects', payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['warehouses'] })
    },
  })
}

export function useUpdateProject() {
  const queryClient = useQueryClient()
  return useMutation<Project, Error, { id: string; payload: Partial<ProjectPayload> }>({
    mutationFn: async ({ id, payload }) => {
      const response = await api.put<Project>(`/projects/${id}`, payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['warehouses'] })
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await api.delete(`/projects/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['warehouses'] })
    },
  })
}
