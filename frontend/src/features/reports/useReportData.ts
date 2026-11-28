import { useQuery, useMutation } from '@tanstack/react-query'
import api from '@/lib/api'
import type {
  TrialBalanceResponse,
  InTransitReportItem,
  StockBalanceResponse,
} from '@/types'

export interface TrialBalanceFilterParams {
  page?: number
  page_size?: number
  date_from?: string
  date_to?: string
  warehouse_id?: string
  project_id?: string
  item_id?: string
  category_id?: string
  transaction_type?: string
  search?: string
}

export interface TrialBalanceExportParams extends TrialBalanceFilterParams {
  view?: 'remaining'
}

export interface InTransitFilterParams {
  source_warehouse_id?: string
  destination_warehouse_id?: string
  status?: string
  search?: string
}

export interface StockBalancesFilterParams {
  warehouse_id?: string
  category_id?: string
  search?: string
}

export function useTrialBalance(filters: TrialBalanceFilterParams = {}) {
  const {
    page = 1,
    page_size = 50,
    date_from,
    date_to,
    warehouse_id,
    project_id,
    item_id,
    category_id,
    transaction_type,
    search,
  } = filters

  return useQuery<TrialBalanceResponse>({
    queryKey: [
      'reports',
      'trial-balance',
      {
        page,
        page_size,
        date_from,
        date_to,
        warehouse_id,
        project_id,
        item_id,
        category_id,
        transaction_type,
        search,
      },
    ],
    queryFn: async () => {
      const params: Record<string, string | number> = { page, page_size }

      if (date_from) params.date_from = date_from
      if (date_to) params.date_to = date_to
      if (warehouse_id) params.warehouse_id = warehouse_id
      if (project_id) params.project_id = project_id
      if (item_id) params.item_id = item_id
      if (category_id) params.category_id = category_id
      if (transaction_type && transaction_type !== 'ALL') {
        params.transaction_type = transaction_type
      }
      if (search && search.trim()) params.search = search.trim()

      const response = await api.get<TrialBalanceResponse>('/reports/trial-balance', {
        params,
      })
      return response.data
    },
    staleTime: 30 * 1000,
  })
}

export function useExportTrialBalance() {
  return useMutation<void, Error, TrialBalanceExportParams>({
    mutationFn: async (filters) => {
      const params: Record<string, string | number> = {}

      if (filters.date_from) params.date_from = filters.date_from
      if (filters.date_to) params.date_to = filters.date_to
      if (filters.warehouse_id) params.warehouse_id = filters.warehouse_id
      if (filters.project_id) params.project_id = filters.project_id
      if (filters.item_id) params.item_id = filters.item_id
      if (filters.category_id) params.category_id = filters.category_id
      if (filters.transaction_type && filters.transaction_type !== 'ALL') {
        params.transaction_type = filters.transaction_type
      }
      if (filters.search && filters.search.trim()) {
        params.search = filters.search.trim()
      }
      if (filters.view) {
        params.view = filters.view
      }

      const response = await api.get('/reports/trial-balance/export', {
        params,
        responseType: 'blob',
      })

      // Create blob download
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl

      const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '')
      const filename =
        filters.view === 'remaining'
          ? `remaining_stock_${dateStr}.xlsx`
          : `trial_balance_${dateStr}.xlsx`
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(downloadUrl)
    },
  })
}

export function useInTransitReport(filters: InTransitFilterParams = {}) {
  const { source_warehouse_id, destination_warehouse_id, status, search } = filters

  return useQuery<InTransitReportItem[]>({
    queryKey: [
      'reports',
      'in-transit',
      { source_warehouse_id, destination_warehouse_id, status, search },
    ],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (source_warehouse_id) params.source_warehouse_id = source_warehouse_id
      if (destination_warehouse_id) {
        params.destination_warehouse_id = destination_warehouse_id
      }
      if (status && status !== 'ALL') params.status = status
      if (search && search.trim()) params.search = search.trim()

      const response = await api.get<InTransitReportItem[]>('/reports/in-transit', {
        params,
      })
      return response.data || []
    },
    staleTime: 15 * 1000,
  })
}

export function useStockBalances(filters: StockBalancesFilterParams = {}) {
  const { warehouse_id, category_id, search } = filters

  return useQuery<StockBalanceResponse>({
    queryKey: ['reports', 'stock-balances', { warehouse_id, category_id, search }],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (warehouse_id) params.warehouse_id = warehouse_id
      if (category_id) params.category_id = category_id
      if (search && search.trim()) params.search = search.trim()

      const response = await api.get<StockBalanceResponse>('/reports/stock-balances', {
        params,
      })
      return response.data
    },
    staleTime: 30 * 1000,
  })
}
