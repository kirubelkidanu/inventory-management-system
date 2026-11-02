import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Search, Loader2, X, Check, ChevronsUpDown, Package } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import type { Item } from '@/types'
import { cn } from '@/lib/utils'

export interface ItemComboboxProps {
  value: string
  onChange: (itemId: string, item?: Item) => void
  disabled?: boolean
  required?: boolean
  placeholder?: string
  error?: boolean
  className?: string
  excludeItemIds?: string[]
}

export const ItemCombobox: React.FC<ItemComboboxProps> = ({
  value,
  onChange,
  disabled = false,
  required = false,
  placeholder = 'Select or search SKU...',
  error = false,
  className,
  excludeItemIds = [],
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [highlightedIndex, setHighlightedIndex] = useState(0)

  const containerRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // Debounce search query (~250ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery)
      setHighlightedIndex(0)
    }, 250)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Fetch active items matching search query (50 per search page)
  const { data, isLoading, isFetching } = useQuery<{ items: Item[]; total: number }>({
    queryKey: ['items-search', debouncedQuery],
    queryFn: async () => {
      const response = await api.get<Item[]>('/items', {
        params: {
          search: debouncedQuery.trim() || undefined,
          page_size: 50,
          is_active: true,
        },
      })
      const items = response.data || []
      const headerTotal = response.headers?.['x-total-count']
      const total = headerTotal !== undefined && headerTotal !== null
        ? parseInt(String(headerTotal), 10)
        : items.length
      return { items, total }
    },
    staleTime: 30 * 1000,
  })

  const fetchedItems = data?.items || []
  const totalCount = data?.total || 0

  // If a value is selected, fetch single item detail if not present in current search results
  const isValueInFetched = fetchedItems.some((i) => i.id === value)
  const { data: itemDetail } = useQuery<Item>({
    queryKey: ['item-detail', value],
    queryFn: async () => {
      const response = await api.get<Item>(`/items/${value}`)
      return response.data
    },
    enabled: Boolean(value && !isValueInFetched),
    staleTime: 60 * 1000,
  })

  const selectedItem = useMemo(() => {
    if (!value) return null
    return fetchedItems.find((i) => i.id === value) || itemDetail || null
  }, [value, fetchedItems, itemDetail])

  // Click outside listener
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick)
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
    }
  }, [isOpen])

  // Focus search input when popover opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        searchInputRef.current?.focus()
      }, 50)
    } else {
      setSearchQuery('')
      setDebouncedQuery('')
      setHighlightedIndex(0)
    }
  }, [isOpen])

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      if (e.key === 'Enter' || e.key === 'ArrowDown' || e.key === ' ') {
        e.preventDefault()
        setIsOpen(true)
      }
      return
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (fetchedItems.length > 0) {
        setHighlightedIndex((prev) => {
          const next = prev < fetchedItems.length - 1 ? prev + 1 : 0
          scrollItemIntoView(next)
          return next
        })
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (fetchedItems.length > 0) {
        setHighlightedIndex((prev) => {
          const next = prev > 0 ? prev - 1 : fetchedItems.length - 1
          scrollItemIntoView(next)
          return next
        })
      }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (fetchedItems.length > 0 && fetchedItems[highlightedIndex]) {
        handleSelectItem(fetchedItems[highlightedIndex])
      }
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setIsOpen(false)
    }
  }

  const scrollItemIntoView = (index: number) => {
    if (listRef.current) {
      const element = listRef.current.children[index] as HTMLElement | undefined
      if (element) {
        element.scrollIntoView({ block: 'nearest' })
      }
    }
  }

  const handleSelectItem = (item: Item) => {
    onChange(item.id, item)
    setIsOpen(false)
    setSearchQuery('')
  }

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onChange('', undefined)
    setSearchQuery('')
  }

  return (
    <div className="relative w-full" ref={containerRef} onKeyDown={handleKeyDown}>
      {/* Hidden input for form validation if required */}
      {required && (
        <input
          type="text"
          value={value}
          readOnly
          tabIndex={-1}
          required={required}
          className="sr-only"
        />
      )}

      {/* Main Trigger Button */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen((prev) => !prev)}
        className={cn(
          'flex w-full items-center justify-between rounded-lg border border-slate-300 bg-white py-2 px-3 text-left text-xs shadow-xs transition-colors hover:border-slate-400 focus:border-sky-500 focus:outline-hidden',
          disabled && 'bg-slate-100 cursor-not-allowed text-slate-400 hover:border-slate-300',
          error && 'border-rose-400 focus:border-rose-500',
          isOpen && 'border-sky-500 ring-2 ring-sky-100',
          className
        )}
      >
        <div className="flex items-center gap-2 overflow-hidden flex-1 mr-1">
          {selectedItem ? (
            <>
              <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-bold text-slate-900 shrink-0">
                {selectedItem.item_code}
              </span>
              <span className="truncate text-slate-800 text-xs" title={selectedItem.description}>
                {selectedItem.description}
              </span>
              <span className="font-mono text-[10px] text-slate-400 shrink-0">
                ({selectedItem.default_unit})
              </span>
            </>
          ) : (
            <span className="text-slate-400 text-xs flex items-center gap-1.5">
              <Package className="h-3.5 w-3.5 text-slate-300" />
              <span>{placeholder}</span>
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0 text-slate-400">
          {selectedItem && !disabled && (
            <span
              role="button"
              tabIndex={0}
              onClick={handleClear}
              title="Clear selection"
              className="rounded p-0.5 hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
            >
              <X className="h-3.5 w-3.5" />
            </span>
          )}
          <ChevronsUpDown className="h-3.5 w-3.5" />
        </div>
      </button>

      {/* Search Popover / Dropdown Overlay */}
      {isOpen && (
        <div className="absolute left-0 top-full mt-1.5 z-50 w-full min-w-[340px] max-w-[560px] rounded-xl border border-slate-200 bg-white shadow-2xl animate-in fade-in zoom-in-95 duration-150">
          {/* Search Input Bar */}
          <div className="relative border-b border-slate-100 p-2.5">
            <Search className="pointer-events-none absolute inset-y-0 left-0 my-auto ml-4 h-4 w-4 text-slate-400" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by SKU code (e.g. 01-CM) or description..."
              className="block w-full rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-9 pr-8 text-xs placeholder-slate-400 focus:border-sky-500 focus:bg-white focus:outline-hidden"
            />
            {isFetching ? (
              <div className="absolute inset-y-0 right-0 mr-4 flex items-center">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-500" />
              </div>
            ) : searchQuery ? (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute inset-y-0 right-0 mr-4 flex items-center text-slate-400 hover:text-slate-600"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            ) : null}
          </div>

          {/* Results List */}
          <div ref={listRef} className="max-h-60 overflow-y-auto divide-y divide-slate-100 py-1">
            {isLoading ? (
              <div className="flex items-center justify-center gap-2 py-6 text-xs text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin text-sky-500" />
                <span>Loading catalog items...</span>
              </div>
            ) : fetchedItems.length === 0 ? (
              <div className="py-6 px-4 text-center">
                <Package className="mx-auto h-6 w-6 text-slate-300" />
                <p className="mt-1 text-xs font-medium text-slate-600">
                  {searchQuery ? `No items found matching "${searchQuery}"` : 'No active items available'}
                </p>
                <p className="mt-0.5 text-[11px] text-slate-400">
                  Try checking the SKU code format or keyword spelling.
                </p>
              </div>
            ) : (
              fetchedItems.map((item, idx) => {
                const isSelected = item.id === value
                const isHighlighted = idx === highlightedIndex
                const isExcluded = excludeItemIds.includes(item.id) && !isSelected

                return (
                  <div
                    key={item.id}
                    onClick={() => !isExcluded && handleSelectItem(item)}
                    onMouseEnter={() => setHighlightedIndex(idx)}
                    className={cn(
                      'flex items-center justify-between px-3 py-2 text-xs transition-colors cursor-pointer',
                      isHighlighted && 'bg-sky-50/70',
                      isSelected && 'bg-sky-100/50 font-medium',
                      isExcluded && 'opacity-40 cursor-not-allowed bg-slate-50'
                    )}
                  >
                    <div className="flex items-center gap-2 overflow-hidden flex-1 mr-2">
                      <span className="inline-flex rounded-md border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-bold text-slate-900 shrink-0">
                        {item.item_code}
                      </span>
                      <span
                        className="truncate text-slate-700"
                        title={item.description}
                      >
                        {item.description}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className="font-mono text-[10px] text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                        {item.default_unit}
                      </span>
                      {isExcluded && (
                        <span className="text-[10px] text-amber-600 italic">Already added</span>
                      )}
                      {isSelected && <Check className="h-4 w-4 text-sky-600 shrink-0" />}
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Footer Metadata */}
          <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/80 px-3 py-1.5 text-[11px] text-slate-500">
            <span>
              {debouncedQuery
                ? `Found ${totalCount} matching item${totalCount === 1 ? '' : 's'}`
                : `Showing ${fetchedItems.length} active items (type to search 5,646+ items)`}
            </span>
            <span className="text-[10px] text-slate-400">Esc to close</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default ItemCombobox
