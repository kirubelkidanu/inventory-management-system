import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import type {
  Item,
  Warehouse,
  Project,
  InTransitReportItem,
  ReconciliationDiscrepancy,
  TrialBalanceResponse,
} from '@/types'

export interface DashboardMetrics {
  totalCatalogItems: number
  activeWarehousesCount: number
  activeProjectsCount: number
  inTransitBatchesCount: number
  reconciliationDiscrepanciesCount: number
  hasDiscrepancies: boolean
}

export function useDashboardData() {
  // 1. Total Catalog Items
  const itemsQuery = useQuery<Item[]>({
    queryKey: ['dashboard', 'items'],
    queryFn: async () => {
      const response = await api.get<Item[]>('/items')
      return response.data
    },
    staleTime: 60 * 1000,
  })

  // 2. Active Warehouses
  const warehousesQuery = useQuery<Warehouse[]>({
    queryKey: ['dashboard', 'warehouses'],
    queryFn: async () => {
      const response = await api.get<Warehouse[]>('/warehouses')
      return response.data
    },
    staleTime: 60 * 1000,
  })

  // 3. Active Projects
  const projectsQuery = useQuery<Project[]>({
    queryKey: ['dashboard', 'projects'],
    queryFn: async () => {
      const response = await api.get<Project[]>('/projects')
      return response.data
    },
    staleTime: 60 * 1000,
  })

  // 4. In-Transit Transfer Batches
  const inTransitQuery = useQuery<InTransitReportItem[]>({
    queryKey: ['dashboard', 'in-transit'],
    queryFn: async () => {
      const response = await api.get<InTransitReportItem[]>('/reports/in-transit')
      return response.data
    },
    staleTime: 30 * 1000,
  })

  // 5. Reconciliation Discrepancies
  const reconciliationQuery = useQuery<ReconciliationDiscrepancy[]>({
    queryKey: ['dashboard', 'reconciliation'],
    queryFn: async () => {
      const response = await api.get<ReconciliationDiscrepancy[]>('/inventory/reconciliation')
      return response.data
    },
    staleTime: 30 * 1000,
  })

  // 6. Recent Transaction Activity (from Trial Balance report)
  const recentActivityQuery = useQuery<TrialBalanceResponse>({
    queryKey: ['dashboard', 'recent-activity'],
    queryFn: async () => {
      const response = await api.get<TrialBalanceResponse>(
        '/reports/trial-balance?page=1&page_size=8'
      )
      return response.data
    },
    staleTime: 15 * 1000,
  })

  const isLoading =
    itemsQuery.isLoading ||
    warehousesQuery.isLoading ||
    projectsQuery.isLoading ||
    inTransitQuery.isLoading ||
    reconciliationQuery.isLoading ||
    recentActivityQuery.isLoading

  const isError =
    itemsQuery.isError ||
    warehousesQuery.isError ||
    projectsQuery.isError ||
    inTransitQuery.isError ||
    reconciliationQuery.isError ||
    recentActivityQuery.isError

  // Fallback demo data if backend queries are empty or loading
  const totalCatalogItems = itemsQuery.data ? itemsQuery.data.length : 1420
  const activeWarehousesCount = warehousesQuery.data
    ? warehousesQuery.data.filter((w) => w.is_active).length
    : 4
  const activeProjectsCount = projectsQuery.data
    ? projectsQuery.data.filter((p) => p.is_active).length
    : 3
  const inTransitItems = inTransitQuery.data || []
  const inTransitBatchesCount = inTransitItems.length
  const reconciliationDiscrepancies = reconciliationQuery.data || []
  const reconciliationDiscrepanciesCount = reconciliationDiscrepancies.length
  const recentMovements = recentActivityQuery.data?.items || []

  const metrics: DashboardMetrics = {
    totalCatalogItems,
    activeWarehousesCount,
    activeProjectsCount,
    inTransitBatchesCount,
    reconciliationDiscrepanciesCount,
    hasDiscrepancies: reconciliationDiscrepanciesCount > 0,
  }

  const refetchAll = () => {
    itemsQuery.refetch()
    warehousesQuery.refetch()
    projectsQuery.refetch()
    inTransitQuery.refetch()
    reconciliationQuery.refetch()
    recentActivityQuery.refetch()
  }

  return {
    metrics,
    items: itemsQuery.data || [],
    warehouses: warehousesQuery.data || [],
    projects: projectsQuery.data || [],
    inTransitItems,
    reconciliationDiscrepancies,
    recentMovements,
    isLoading,
    isError,
    refetchAll,
  }
}
