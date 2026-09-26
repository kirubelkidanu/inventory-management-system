import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type {
  Transaction,
  Project,
  InTransitReportItem,
} from '@/types'

// ---------------------------------------------------------------------------
// DTO Schemas
// ---------------------------------------------------------------------------

export interface TransactionLineInput {
  item_id: string
  quantity: number
  unit: string
  remarks?: string
}

export interface GRVCreatePayload {
  warehouse_id: string
  project_id?: string | null
  transaction_date: string
  supplier_name?: string | null
  invoice_no?: string | null
  received_grv_no?: string | null
  store_no?: string | null
  remarks?: string | null
  lines: TransactionLineInput[]
}

export interface SIVCreatePayload {
  warehouse_id: string
  project_id?: string | null
  transaction_date: string
  requested_from?: string | null
  project_dept?: string | null
  requested_no?: string | null
  siv_no?: string | null
  material_summary?: string | null
  issued_by_name?: string | null
  checked_by_name?: string | null
  received_by_name?: string | null
  approved_by_name?: string | null
  remarks?: string | null
  lines: TransactionLineInput[]
}

export interface ISTVCreatePayload {
  source_warehouse_id: string
  destination_warehouse_id: string
  project_id?: string | null
  transaction_date: string
  istv_no?: string | null
  plate_no?: string | null
  driver_name?: string | null
  material_summary?: string | null
  remarks?: string | null
  lines: TransactionLineInput[]
}

export interface ISTRVLineInput {
  item_id: string
  quantity: number
  remarks?: string
}

export interface ISTRVCreatePayload {
  istv_transaction_id: string
  destination_warehouse_id: string
  transaction_date: string
  remarks?: string | null
  lines: ISTRVLineInput[]
}

export interface SRVLineInput {
  item_id: string
  quantity: number
  unit: string
  remarks?: string
}

export interface SRVCreatePayload {
  reference_siv_id: string
  warehouse_id: string
  project_id?: string | null
  transaction_date: string
  remarks?: string | null
  lines: SRVLineInput[]
}

export interface AdjustmentLineInput {
  item_id: string
  direction: 'IN' | 'OUT'
  quantity: number
  unit: string
  remarks?: string
}

export interface AdjustmentCreatePayload {
  warehouse_id: string
  project_id?: string | null
  transaction_date: string
  adjustment_reason: string
  remarks?: string | null
  lines: AdjustmentLineInput[]
}

export interface TransactionFilterParams {
  transaction_type?: string
  warehouse_id?: string
  search?: string
  skip?: number
  limit?: number
}

// ---------------------------------------------------------------------------
// Error Extractor Utility
// ---------------------------------------------------------------------------

export function extractErrorMessage(error: any): string {
  if (!error) return 'An unexpected error occurred.'

  const data = error.response?.data
  if (data) {
    if (typeof data.detail === 'string') {
      return data.detail
    }
    if (Array.isArray(data.detail)) {
      // FastAPI ValidationError format
      return data.detail.map((err: any) => `${err.loc?.slice(-1)[0] || 'Field'}: ${err.msg}`).join(', ')
    }
    if (typeof data.message === 'string') {
      return data.message
    }
  }

  if (error.message) {
    return error.message
  }

  return 'Operation failed. Please verify the input values.'
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useProjects() {
  return useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await api.get<Project[]>('/projects')
      return response.data || []
    },
    staleTime: 60 * 1000,
  })
}

export function useTransactions(params: TransactionFilterParams = {}) {
  const { transaction_type, warehouse_id, search, skip = 0, limit = 50 } = params

  return useQuery<Transaction[]>({
    queryKey: ['transactions', { transaction_type, warehouse_id, search, skip, limit }],
    queryFn: async () => {
      const queryParams: Record<string, string | number> = { skip, limit }
      if (transaction_type && transaction_type !== 'ALL') {
        queryParams.transaction_type = transaction_type
      }
      if (warehouse_id) {
        queryParams.warehouse_id = warehouse_id
      }
      if (search && search.trim()) {
        queryParams.search = search.trim()
      }

      const response = await api.get<Transaction[]>('/transactions', {
        params: queryParams,
      })
      return response.data || []
    },
    staleTime: 10 * 1000,
  })
}

export function useTransaction(transactionId?: string) {
  return useQuery<Transaction>({
    queryKey: ['transactions', transactionId],
    queryFn: async () => {
      if (!transactionId) throw new Error('Transaction ID is required')
      const response = await api.get<Transaction>(`/transactions/${transactionId}`)
      return response.data
    },
    enabled: Boolean(transactionId),
  })
}

export function useInTransitTransfers(destinationWarehouseId?: string) {
  return useQuery<InTransitReportItem[]>({
    queryKey: ['in-transit-transfers', { destinationWarehouseId }],
    queryFn: async () => {
      const queryParams: Record<string, string> = {}
      if (destinationWarehouseId) {
        queryParams.destination_warehouse_id = destinationWarehouseId
      }
      const response = await api.get<InTransitReportItem[]>('/reports/in-transit', {
        params: queryParams,
      })
      return response.data || []
    },
    staleTime: 15 * 1000,
  })
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreateGRV() {
  const queryClient = useQueryClient()

  return useMutation<Transaction, Error, GRVCreatePayload>({
    mutationFn: async (payload) => {
      const response = await api.post<Transaction>('/transactions/grv', payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

export function useCreateSIV() {
  const queryClient = useQueryClient()

  return useMutation<Transaction, Error, SIVCreatePayload>({
    mutationFn: async (payload) => {
      const response = await api.post<Transaction>('/transactions/siv', payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

export function useCreateISTV() {
  const queryClient = useQueryClient()

  return useMutation<Transaction, Error, ISTVCreatePayload>({
    mutationFn: async (payload) => {
      const response = await api.post<Transaction>('/transactions/istv', payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      queryClient.invalidateQueries({ queryKey: ['in-transit-transfers'] })
    },
  })
}

export function useCreateISTRV() {
  const queryClient = useQueryClient()

  return useMutation<Transaction, Error, ISTRVCreatePayload>({
    mutationFn: async (payload) => {
      const response = await api.post<Transaction>('/transactions/istrv', payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      queryClient.invalidateQueries({ queryKey: ['in-transit-transfers'] })
    },
  })
}

export function useCreateSRV() {
  const queryClient = useQueryClient()

  return useMutation<Transaction, Error, SRVCreatePayload>({
    mutationFn: async (payload) => {
      const response = await api.post<Transaction>('/transactions/srv', payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

export function useCreateAdjustment() {
  const queryClient = useQueryClient()

  return useMutation<Transaction, Error, AdjustmentCreatePayload>({
    mutationFn: async (payload) => {
      const response = await api.post<Transaction>('/transactions/adjustment', payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}
