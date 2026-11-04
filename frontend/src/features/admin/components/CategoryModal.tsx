import React, { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { X, Loader2, AlertCircle, FolderTree } from 'lucide-react'
import type { Category } from '@/types'
import { useCreateCategory, useUpdateCategory } from '@/features/inventory/useInventoryData'

const categorySchema = z.object({
  code: z
    .string()
    .trim()
    .min(1, 'Category code is required (1-50 characters)')
    .max(50, 'Category code cannot exceed 50 characters')
    .regex(/^[A-Za-z0-9_-]+$/, 'Code must contain only letters, numbers, hyphens, and underscores'),
  name: z
    .string()
    .trim()
    .min(1, 'Category name is required (1-255 characters)')
    .max(255, 'Category name cannot exceed 255 characters'),
  description: z.string().optional(),
  is_active: z.boolean().default(true),
})

type CategoryFormData = z.infer<typeof categorySchema>

interface CategoryModalProps {
  isOpen: boolean
  onClose: () => void
  category?: Category | null
}

export const CategoryModal: React.FC<CategoryModalProps> = ({
  isOpen,
  onClose,
  category,
}) => {
  const isEditing = Boolean(category)
  const createMutation = useCreateCategory()
  const updateMutation = useUpdateCategory()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<CategoryFormData>({
    resolver: zodResolver(categorySchema),
    defaultValues: {
      code: '',
      name: '',
      description: '',
      is_active: true,
    },
  })

  useEffect(() => {
    if (isOpen) {
      setServerError(null)
      if (category) {
        reset({
          code: category.code,
          name: category.name,
          description: category.description || '',
          is_active: category.is_active,
        })
      } else {
        reset({
          code: '',
          name: '',
          description: '',
          is_active: true,
        })
      }
    }
  }, [isOpen, category, reset])

  if (!isOpen) return null

  const onSubmit = async (data: CategoryFormData) => {
    setServerError(null)
    try {
      if (isEditing && category) {
        await updateMutation.mutateAsync({
          id: category.id,
          data: {
            name: data.name.trim(),
            description: data.description?.trim() || null,
            is_active: data.is_active,
          },
        })
      } else {
        await createMutation.mutateAsync({
          code: data.code.trim().toUpperCase(),
          name: data.name.trim(),
          description: data.description?.trim() || null,
          is_active: data.is_active,
        })
      }
      onClose()
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'An error occurred.'
      if (err.response?.status === 409 || detail.toLowerCase().includes('already exists')) {
        setError('code', { message: 'Category code already exists in catalog.' })
        setServerError('Category code already exists in catalog.')
      } else {
        setServerError(typeof detail === 'string' ? detail : 'Failed to save category.')
      }
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending || isSubmitting

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
      <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in duration-200">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-blue-100 text-blue-700 rounded-lg">
              <FolderTree className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                {isEditing ? 'Edit Category' : 'Create New Category'}
              </h3>
              <p className="text-xs text-slate-500">
                {isEditing
                  ? `Editing category details for code ${category?.code}`
                  : 'Define a new inventory classification and SKU prefix'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4">
          {serverError && (
            <div className="flex items-start gap-2.5 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{serverError}</span>
            </div>
          )}

          {/* Category Code */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Category Code <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. 15, 17, 01-CM"
              disabled={isEditing || isPending}
              {...register('code')}
              className={`w-full px-3 py-2 text-sm font-mono border rounded-lg focus:outline-none focus:ring-2 uppercase transition-all ${
                isEditing
                  ? 'bg-slate-100 text-slate-500 border-slate-200 cursor-not-allowed'
                  : errors.code
                  ? 'border-red-300 focus:ring-red-400 bg-red-50/30'
                  : 'border-slate-300 focus:ring-blue-500 bg-white'
              }`}
            />
            {errors.code && (
              <p className="mt-1 text-xs text-red-600 font-medium">{errors.code.message}</p>
            )}
            <p className="mt-1 text-[11px] text-slate-400">
              {isEditing
                ? 'Category code cannot be modified once created.'
                : 'Primary identifier and prefix reference (e.g. 01, 15, 17).'}
            </p>
          </div>

          {/* Category Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Category Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. STATIONERY, CLEANING MATERIALS"
              disabled={isPending}
              {...register('name')}
              className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 transition-all ${
                errors.name
                  ? 'border-red-300 focus:ring-red-400 bg-red-50/30'
                  : 'border-slate-300 focus:ring-blue-500 bg-white'
              }`}
            />
            {errors.name && (
              <p className="mt-1 text-xs text-red-600 font-medium">{errors.name.message}</p>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Description (Optional)
            </label>
            <textarea
              rows={3}
              placeholder="Brief description of materials, spare parts, or items classified in this category..."
              disabled={isPending}
              {...register('description')}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white transition-all resize-none"
            />
          </div>

          {/* Active Status Checkbox */}
          <div className="pt-1">
            <label className="flex items-center gap-2.5 cursor-pointer select-none">
              <input
                type="checkbox"
                disabled={isPending}
                {...register('is_active')}
                className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
              <div>
                <span className="text-sm font-semibold text-slate-800">Active Status</span>
                <p className="text-xs text-slate-500">
                  Active categories appear in item forms and import mapping. Inactive categories are archived.
                </p>
              </div>
            </label>
          </div>

          {/* Modal Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={isPending}
              className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors disabled:opacity-50"
            >
              {isPending && <Loader2 className="w-4 h-4 animate-spin" />}
              <span>{isEditing ? 'Save Changes' : 'Create Category'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default CategoryModal
