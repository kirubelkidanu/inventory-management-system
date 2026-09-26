import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type {
  CountSheetResponse,
  PhysicalCountSubmitRequest,
  ReconciliationPreviewResponse,
  ReconciliationCommitRequest,
  ReconciliationCommitResponse,
} from '@/types'

export function useCountSheet(warehouseId?: string) {
  return useQuery<CountSheetResponse>({
    queryKey: ['reconciliation', 'count-sheet', warehouseId],
    queryFn: async () => {
      if (!warehouseId) throw new Error('Warehouse ID is required')
      const response = await api.get<CountSheetResponse>(
        `/reconciliation/count-sheet/${warehouseId}`
      )
      return response.data
    },
    enabled: Boolean(warehouseId),
    staleTime: 10 * 1000,
  })
}

export function usePreviewVariance() {
  return useMutation<ReconciliationPreviewResponse, Error, PhysicalCountSubmitRequest>({
    mutationFn: async (payload) => {
      const response = await api.post<ReconciliationPreviewResponse>(
        '/reconciliation/preview',
        payload
      )
      return response.data
    },
  })
}

export function useCommitReconciliation() {
  const queryClient = useQueryClient()

  return useMutation<ReconciliationCommitResponse, Error, ReconciliationCommitRequest>({
    mutationFn: async (payload) => {
      const response = await api.post<ReconciliationCommitResponse>(
        '/reconciliation/commit',
        payload
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['reconciliation'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}
