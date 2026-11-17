import React, { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Ban, CheckCircle2, Loader2, X } from 'lucide-react'
import api from '@/lib/api'
import type { TransactionLine } from '@/types'

interface VoidLineModalProps {
  isOpen: boolean
  onClose: () => void
  transactionId: string
  transactionNumber: string
  transactionType: string
  line: TransactionLine | null
  onSuccess?: () => void
}

export const VoidLineModal: React.FC<VoidLineModalProps> = ({
  isOpen,
  onClose,
  transactionId,
  transactionNumber,
  transactionType,
  line,
  onSuccess,
}) => {
  const queryClient = useQueryClient()
  const [reason, setReason] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  if (!isOpen || !line) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const trimmedReason = reason.trim()
    if (!trimmedReason || trimmedReason.length < 3) {
      setError('Please provide a mandatory cancellation reason (at least 3 characters).')
      return
    }

    setIsSubmitting(true)
    try {
      await api.post(`/transactions/${transactionId}/lines/${line.id}/void`, {
        reason: trimmedReason,
      })

      setSuccessMessage(`Line #${line.line_number || ''} successfully voided. Compensating ledger entry recorded.`)

      // Invalidate relevant queries across the application
      queryClient.invalidateQueries({ queryKey: ['transaction'] })
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['trial-balance'] })
      queryClient.invalidateQueries({ queryKey: ['in-transit'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-balances'] })
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      queryClient.invalidateQueries({ queryKey: ['reconciliation'] })

      setTimeout(() => {
        setIsSubmitting(false)
        setSuccessMessage(null)
        setReason('')
        onSuccess?.()
        onClose()
      }, 1000)
    } catch (err: any) {
      setIsSubmitting(false)
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to void transaction line. Please check ledger balance and permissions.'
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail))
    }
  }

  const handleClose = () => {
    if (isSubmitting) return
    setError(null)
    setSuccessMessage(null)
    setReason('')
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 animate-in fade-in">
      <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2 text-rose-700">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-100 text-rose-700">
              <Ban className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Void Transaction Line</h3>
              <p className="text-xs text-slate-500 font-mono">
                {transactionType} {transactionNumber} &bull; Line #{line.line_number}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={isSubmitting}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Line Summary */}
        <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-xs space-y-1.5">
          <div className="flex justify-between">
            <span className="text-slate-500">Item:</span>
            <span className="font-mono font-medium text-slate-900">{line.item?.item_code || line.item_id}</span>
          </div>
          {line.item?.description && (
            <div className="flex justify-between">
              <span className="text-slate-500">Description:</span>
              <span className="text-slate-800 text-right truncate max-w-xs">{line.item.description}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-slate-500">Transacted Quantity:</span>
            <span className="font-mono font-bold text-slate-900">
              {Number(line.quantity).toLocaleString(undefined, { minimumFractionDigits: 2 })} {line.unit}
            </span>
          </div>
          <div className="mt-2 text-[11px] text-amber-700 bg-amber-50 rounded-lg p-2 border border-amber-200">
            <strong>ADR-009 Notice:</strong> Reversing this line will atomically post a compensating ledger movement in stock movements and adjust inventory balances. Historical movements will not be deleted.
          </div>
        </div>

        {/* Success or Error banners */}
        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-600 mt-0.5" />
            <div className="flex-1">{error}</div>
          </div>
        )}

        {successMessage && (
          <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-700">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            <div className="flex-1 font-medium">{successMessage}</div>
          </div>
        )}

        {/* Reason Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Cancellation / Void Reason <span className="text-rose-500">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              disabled={isSubmitting || !!successMessage}
              placeholder="e.g. Data entry error, wrong item specified, duplicate physical voucher line..."
              rows={3}
              className="w-full rounded-xl border border-slate-300 p-2.5 text-xs text-slate-800 focus:border-rose-500 focus:outline-hidden disabled:bg-slate-100"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={handleClose}
              disabled={isSubmitting}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !!successMessage || reason.trim().length < 3}
              className="inline-flex items-center gap-1.5 rounded-lg bg-rose-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-rose-700 disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Voiding Line...</span>
                </>
              ) : (
                <>
                  <Ban className="h-3.5 w-3.5" />
                  <span>Confirm Void Line</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default VoidLineModal
