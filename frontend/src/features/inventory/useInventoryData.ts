import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type {
  Item,
  ItemDeleteResult,
  ItemBulkDeleteResult,
  Category,
  Warehouse,
  InventoryBalance,
  StockMovement,
  ImportBatchPreviewResponse,
  CommitBatchResponse,
  ImportBatch,
  InitialStockBatchPreviewResponse,
  CommitInitialStockResponse,
  OpeningBalanceCreateInput,
  Transaction,
} from '@/types'

export interface ItemQueryParams {
  search?: string
  category_id?: string
  include_inactive?: boolean
  skip?: number
  limit?: number
}

export interface BalanceQueryParams {
  warehouse_id?: string
  category_id?: string
  item_id?: string
  search?: string
  include_inactive_warehouses?: boolean
  skip?: number
  limit?: number
}

export interface EnrichedInventoryBalance extends InventoryBalance {
  item_code: string
  item_description: string
  category_id?: string
  category_name: string
  unit: string
  warehouse_code: string
  warehouse_name: string
  warehouse_is_active?: boolean
}

export interface ItemCreatePayload {
  item_code: string
  description: string
  category_id: string
  default_unit: string
  is_active?: boolean
}

export interface ItemUpdatePayload {
  description?: string
  category_id?: string
  default_unit?: string
  is_active?: boolean
}

export function useCategories() {
  return useQuery<Category[]>({
    queryKey: ['categories'],
    queryFn: async () => {
      const response = await api.get<Category[]>('/categories')
      return response.data
    },
    staleTime: 60 * 1000,
  })
}

export function useWarehouses() {
  return useQuery<Warehouse[]>({
    queryKey: ['warehouses'],
    queryFn: async () => {
      const response = await api.get<Warehouse[]>('/warehouses')
      return response.data
    },
    staleTime: 60 * 1000,
  })
}

export function useItems(params: ItemQueryParams = {}) {
  const { search, category_id, include_inactive = false, skip = 0, limit = 50 } = params

  return useQuery<{ items: Item[]; total: number }>({
    queryKey: ['items', { search, category_id, include_inactive, skip, limit }],
    queryFn: async () => {
      const queryParams: Record<string, string | number | boolean> = {
        include_inactive,
        skip,
        limit,
      }
      if (search && search.trim()) {
        queryParams.search = search.trim()
      }
      if (category_id) {
        queryParams.category_id = category_id
      }

      const response = await api.get<Item[]>('/items', {
        params: queryParams,
      })
      const items = response.data || []
      const headerTotal = response.headers?.['x-total-count']
      const total =
        headerTotal !== undefined && headerTotal !== null
          ? parseInt(String(headerTotal), 10)
          : items.length

      return { items, total }
    },
    staleTime: 30 * 1000,
  })
}

export function useCreateItem() {
  const queryClient = useQueryClient()
  return useMutation<Item, Error, ItemCreatePayload>({
    mutationFn: async (payload: ItemCreatePayload) => {
      const response = await api.post<Item>('/items', payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
    },
  })
}

export function useUpdateItem() {
  const queryClient = useQueryClient()
  return useMutation<Item, Error, { id: string; payload: ItemUpdatePayload }>({
    mutationFn: async ({ id, payload }: { id: string; payload: ItemUpdatePayload }) => {
      const response = await api.put<Item>(`/items/${id}`, payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
    },
  })
}

export function useInventoryBalances(params: BalanceQueryParams = {}) {
  const { warehouse_id, category_id, item_id, search, include_inactive_warehouses } = params

  return useQuery<EnrichedInventoryBalance[]>({
    queryKey: [
      'inventory-balances',
      { warehouse_id, category_id, item_id, search, include_inactive_warehouses },
    ],
    queryFn: async () => {
      const queryParams: Record<string, string | boolean> = {}
      if (warehouse_id) queryParams.warehouse_id = warehouse_id
      if (category_id) queryParams.category_id = category_id
      if (item_id) queryParams.item_id = item_id
      if (search) queryParams.search = search
      if (include_inactive_warehouses) queryParams.include_inactive_warehouses = true

      const response = await api.get<InventoryBalance[]>('/inventory/balances', {
        params: queryParams,
      })

      const rawBalances = response.data || []

      return rawBalances.map((b) => {
        const onHand = Number(b.quantity_on_hand) || 0
        const reserved = Number(b.quantity_reserved) || 0
        const available =
          b.available_quantity !== undefined && b.available_quantity !== null
            ? Number(b.available_quantity)
            : onHand - reserved

        return {
          ...b,
          quantity_on_hand: onHand,
          quantity_reserved: reserved,
          available_quantity: available,
          item_code: b.item_code || 'SKU-UNKNOWN',
          item_description: b.item_description || 'Item Description',
          category_name: b.category_name || 'General',
          unit: b.unit || 'PCS',
          warehouse_code: b.warehouse_code || 'WH',
          warehouse_name: b.warehouse_name || 'Warehouse',
          warehouse_is_active: b.warehouse_is_active,
        }
      })
    },
    staleTime: 15 * 1000,
  })
}

export function useItemStockMovements(itemId?: string, warehouseId?: string) {
  return useQuery<StockMovement[]>({
    queryKey: ['stock-movements', { itemId, warehouseId }],
    queryFn: async () => {
      if (!itemId) return []
      const queryParams: Record<string, string> = { item_id: itemId }
      if (warehouseId) queryParams.warehouse_id = warehouseId

      const response = await api.get<StockMovement[]>('/inventory/stock-movements', {
        params: queryParams,
      })
      return response.data || []
    },
    enabled: !!itemId,
    staleTime: 15 * 1000,
  })
}

export function useStageItemMaster() {
  return useMutation<ImportBatchPreviewResponse, Error, File>({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const response = await api.post<ImportBatchPreviewResponse>(
        '/imports/items/stage',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 120000,
        }
      )
      return response.data
    },
  })
}

export function useCommitItemMaster() {
  const queryClient = useQueryClient()
  return useMutation<CommitBatchResponse, Error, string>({
    mutationFn: async (batchId: string) => {
      const response = await api.post<CommitBatchResponse>(
        `/imports/items/${batchId}/commit`,
        null,
        {
          timeout: 120000,
        }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
    },
  })
}

export function useStageInitialStock() {
  return useMutation<
    InitialStockBatchPreviewResponse,
    Error,
    { file: File; warehouseId?: string; warehouse_id?: string; projectId?: string; project_id?: string; transactionDate?: string; transaction_date?: string; remarks?: string }
  >({
    mutationFn: async ({ file, warehouseId, warehouse_id, projectId, project_id, transactionDate, transaction_date, remarks }) => {
      const formData = new FormData()
      formData.append('file', file)
      const targetWh = warehouseId || warehouse_id || ''
      if (targetWh) formData.append('warehouse_id', targetWh)
      const targetProj = projectId || project_id
      if (targetProj) formData.append('project_id', targetProj)
      const targetDate = transactionDate || transaction_date
      if (targetDate) formData.append('transaction_date', targetDate)
      if (remarks) formData.append('remarks', remarks)

      const stageRes = await api.post<ImportBatch>('/imports/initial-stock/stage', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000,
      })

      const previewRes = await api.get<InitialStockBatchPreviewResponse>(
        `/imports/initial-stock/${stageRes.data.id}`
      )
      return previewRes.data
    },
  })
}

export function useCommitInitialStock() {
  const queryClient = useQueryClient()
  return useMutation<CommitInitialStockResponse, Error, string>({
    mutationFn: async (batchId: string) => {
      const response = await api.post<CommitInitialStockResponse>(
        `/imports/initial-stock/${batchId}/commit`,
        null,
        {
          timeout: 120000,
        }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
      queryClient.invalidateQueries({ queryKey: ['trial-balance'] })
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['import-batches'] })
      queryClient.invalidateQueries({ queryKey: ['initial-stock-batches'] })
      queryClient.invalidateQueries({ queryKey: ['opening-balance-transactions'] })
    },
  })
}

export function useCreateManualOpeningBalance() {
  const queryClient = useQueryClient()
  return useMutation<Transaction, Error, OpeningBalanceCreateInput>({
    mutationFn: async (payload: OpeningBalanceCreateInput) => {
      const response = await api.post<Transaction>('/transactions/opening-balance', payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
      queryClient.invalidateQueries({ queryKey: ['trial-balance'] })
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['import-batches'] })
      queryClient.invalidateQueries({ queryKey: ['initial-stock-batches'] })
      queryClient.invalidateQueries({ queryKey: ['opening-balance-transactions'] })
    },
  })
}

export function useInitialStockBatches() {
  return useQuery<ImportBatch[]>({
    queryKey: ['initial-stock-batches'],
    queryFn: async () => {
      const response = await api.get<ImportBatch[]>('/imports/initial-stock/batches')
      return response.data || []
    },
    staleTime: 30 * 1000,
  })
}

export function useOpeningBalanceTransactions() {
  return useQuery<Transaction[]>({
    queryKey: ['opening-balance-transactions'],
    queryFn: async () => {
      const response = await api.get<Transaction[]>('/transactions', {
        params: {
          transaction_type: 'ADJUSTMENT',
          external_reference: 'OPENING_BALANCE',
          limit: 100,
        },
      })
      return response.data || []
    },
    staleTime: 30 * 1000,
  })
}


export function useDeleteItem() {
  const queryClient = useQueryClient()
  return useMutation<ItemDeleteResult, Error, string>({
    mutationFn: async (itemId: string) => {
      const response = await api.delete<ItemDeleteResult>('/items/' + itemId)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
    },
  })
}

export function useBulkDeleteItems() {
  const queryClient = useQueryClient()
  return useMutation<ItemBulkDeleteResult, Error, string[]>({
    mutationFn: async (itemIds: string[]) => {
      const response = await api.post<ItemBulkDeleteResult>('/items/bulk-delete', {
        item_ids: itemIds,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
    },
  })
}

export function useRestoreItem() {
  const queryClient = useQueryClient()
  return useMutation<Item, Error, string>({
    mutationFn: async (itemId: string) => {
      const response = await api.patch<Item>('/items/' + itemId + '/restore')
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
    },
  })
}
