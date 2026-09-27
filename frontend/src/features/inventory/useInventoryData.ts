import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type {
  Item,
  Category,
  Warehouse,
  InventoryBalance,
  StockMovement,
  ImportBatchPreviewResponse,
  CommitBatchResponse,
} from '@/types'

export interface ItemQueryParams {
  search?: string
  category_id?: string
  skip?: number
  limit?: number
}

export interface BalanceQueryParams {
  warehouse_id?: string
  category_id?: string
  item_id?: string
  search?: string
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
  const { search, category_id, skip = 0, limit = 50 } = params

  return useQuery<{ items: Item[]; total: number }>({
    queryKey: ['items', { search, category_id, skip, limit }],
    queryFn: async () => {
      const response = await api.get<Item[]>('/items')
      let items = response.data || []

      // Client filter if backend returns full catalog list
      if (category_id) {
        items = items.filter((i) => i.category_id === category_id)
      }
      if (search && search.trim()) {
        const q = search.toLowerCase().trim()
        items = items.filter(
          (i) =>
            i.item_code.toLowerCase().includes(q) ||
            i.description.toLowerCase().includes(q)
        )
      }

      const total = items.length
      const paginated = items.slice(skip, skip + limit)

      return { items: paginated, total }
    },
    staleTime: 30 * 1000,
  })
}

export function useInventoryBalances(params: BalanceQueryParams = {}) {
  const { warehouse_id, category_id, item_id, search } = params
  const { data: items } = useQuery<Item[]>({
    queryKey: ['items', 'all'],
    queryFn: async () => (await api.get<Item[]>('/items')).data,
    staleTime: 60 * 1000,
  })
  const { data: warehouses } = useWarehouses()
  const { data: categories } = useCategories()

  return useQuery<EnrichedInventoryBalance[]>({
    queryKey: ['inventory-balances', { warehouse_id, category_id, item_id, search }],
    queryFn: async () => {
      const queryParams: Record<string, string> = {}
      if (warehouse_id) queryParams.warehouse_id = warehouse_id
      if (category_id) queryParams.category_id = category_id
      if (item_id) queryParams.item_id = item_id
      if (search) queryParams.search = search

      const response = await api.get<InventoryBalance[]>('/inventory/balances', {
        params: queryParams,
      })

      const rawBalances = response.data || []

      const itemMap = new Map((items || []).map((i) => [i.id, i]))
      const warehouseMap = new Map((warehouses || []).map((w) => [w.id, w]))
      const categoryMap = new Map((categories || []).map((c) => [c.id, c.name]))

      return rawBalances.map((b) => {
        const itm = itemMap.get(b.item_id)
        const wh = warehouseMap.get(b.warehouse_id)
        const onHand = Number(b.quantity_on_hand) || 0
        const reserved = Number(b.quantity_reserved) || 0

        return {
          ...b,
          quantity_on_hand: onHand,
          quantity_reserved: reserved,
          available_quantity: onHand - reserved,
          item_code: itm?.item_code || 'SKU-UNKNOWN',
          item_description: itm?.description || 'Item Description',
          category_id: itm?.category_id,
          category_name: itm?.category_id ? categoryMap.get(itm.category_id) || 'General' : 'General',
          unit: itm?.default_unit || 'PCS',
          warehouse_code: wh?.code || 'WH',
          warehouse_name: wh?.name || 'Warehouse',
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
        `/imports/items/${batchId}/commit`
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
    },
  })
}
