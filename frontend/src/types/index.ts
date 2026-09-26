// Domain Interfaces matching backend Pydantic schemas and database models

export type UserRole = 'ADMIN' | 'INVENTORY_MANAGER' | 'STORE_KEEPER' | 'VIEWER'

export interface User {
  id: string
  auth_user_id?: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface Category {
  id: string
  code: string
  name: string
  description?: string | null
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface Warehouse {
  id: string
  code: string
  name: string
  location?: string | null
  default_project_id?: string | null
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface Project {
  id: string
  code: string
  name: string
  description?: string | null
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface Item {
  id: string
  item_code: string
  description: string
  category_id: string
  default_unit: string
  is_active: boolean
  created_at?: string
  updated_at?: string
  category?: Category
}

export interface InventoryBalance {
  id: string
  warehouse_id: string
  item_id: string
  quantity_on_hand: number | string
  quantity_reserved: number | string
  available_quantity?: number | string
  updated_at: string
  warehouse?: Warehouse
  item?: Item
}

export interface StockMovement {
  id: string
  transaction_id: string
  warehouse_id: string
  item_id: string
  movement_type: 'IN' | 'OUT'
  quantity: number | string
  signed_quantity: number | string
  running_balance?: number | string | null
  movement_date: string
  created_at: string
}

export type TransactionType = 'GRV' | 'SIV' | 'ISTV' | 'ISTRV' | 'SRV' | 'ADJUSTMENT'
export type TransactionStatus = 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'POSTED' | 'CANCELLED'

export interface TransactionLine {
  id?: string
  transaction_id?: string
  line_number?: number
  item_id: string
  quantity: number | string
  unit: string
  remarks?: string | null
  item?: Item
}

export interface Transaction {
  id: string
  transaction_number: string
  transaction_type: TransactionType
  status: TransactionStatus
  transaction_date: string
  warehouse_id?: string | null
  source_warehouse_id?: string | null
  destination_warehouse_id?: string | null
  project_id?: string | null
  reference_transaction_id?: string | null
  external_reference?: string | null
  supplier_name?: string | null
  invoice_no?: string | null
  received_grv_no?: string | null
  store_no?: string | null
  requested_from?: string | null
  project_dept?: string | null
  requested_no?: string | null
  siv_no?: string | null
  issued_by_name?: string | null
  checked_by_name?: string | null
  received_by_name?: string | null
  approved_by_name?: string | null
  istv_no?: string | null
  plate_no?: string | null
  driver_name?: string | null
  material_summary?: string | null
  adjustment_reason?: string | null
  remarks?: string | null
  created_by?: string
  created_at?: string
  posted_by?: string | null
  posted_at?: string | null
  lines?: TransactionLine[]
}

export interface TrialBalanceItem {
  movement_id: string
  movement_date: string
  created_at: string
  transaction_id: string
  transaction_number: string
  transaction_type: string
  reference_number?: string | null
  item_id: string
  item_code: string
  item_description: string
  category_name: string
  unit: string
  warehouse_id: string
  warehouse_code: string
  warehouse_name: string
  project_name?: string | null
  plate_no?: string | null
  driver_name?: string | null
  in_quantity: number | string
  out_quantity: number | string
  signed_quantity: number | string
  running_balance?: number | string | null
  status: string
  entered_by_name: string
}

export interface TrialBalanceResponse {
  total_count: number
  page: number
  page_size: number
  items: TrialBalanceItem[]
  total_in: number | string
  total_out: number | string
}

export interface CountSheetItem {
  item_id: string
  item_code: string
  item_description: string
  category_name: string
  unit: string
  system_quantity_on_hand?: number | string
  system_quantity?: number | string
}

export interface CountSheetResponse {
  warehouse_id: string
  warehouse_code: string
  warehouse_name: string
  generated_at?: string
  as_of_date?: string
  total_items?: number
  total_active_items?: number
  items: CountSheetItem[]
}

export interface VarianceItem {
  item_id: string
  item_code: string
  item_description: string
  unit: string
  system_quantity: number | string
  counted_quantity: number | string
  variance_quantity: number | string
  adjustment_direction?: 'IN' | 'OUT' | 'NONE'
  direction?: 'IN' | 'OUT' | 'NONE'
  remarks?: string | null
}

export interface ReconciliationPreviewResponse {
  warehouse_id: string
  warehouse_code: string
  warehouse_name: string
  count_date: string
  count_reference: string
  total_items_counted: number
  matched_items_count?: number
  matched_count?: number
  surplus_items_count?: number
  surplus_count?: number
  deficit_items_count?: number
  deficit_count?: number
  variances?: VarianceItem[]
  lines?: VarianceItem[]
}

export interface PhysicalCountItemInput {
  item_id: string
  counted_quantity: number
  remarks?: string | null
}

export interface PhysicalCountSubmitRequest {
  warehouse_id: string
  count_date: string
  count_reference: string
  remarks?: string | null
  counts: PhysicalCountItemInput[]
}

export interface ReconciliationCommitRequest {
  warehouse_id: string
  count_date: string
  count_reference: string
  adjustment_reason: string
  counts: PhysicalCountItemInput[]
}

export interface ReconciliationCommitResponse {
  message: string
  count_reference: string
  transaction_id: string | null
  transaction_number: string | null
  adjusted_lines_count: number
  warehouse_id: string
}

export interface InTransitReportItem {
  transfer_record_id: string
  istv_transaction_id?: string
  istv_number: string
  transfer_date?: string
  transaction_date?: string
  source_warehouse_id?: string
  source_warehouse_code?: string
  source_warehouse_name: string
  destination_warehouse_id?: string
  destination_warehouse_code?: string
  destination_warehouse_name: string
  plate_no?: string | null
  driver_name?: string | null
  item_id: string
  item_code: string
  item_description: string
  dispatched_quantity?: number | string
  sent_quantity?: number | string
  received_quantity: number | string
  remaining_quantity: number | string
  unit: string
  status: string
}

export interface StockBalanceItem {
  warehouse_id: string
  warehouse_code: string
  warehouse_name: string
  project_name?: string | null
  category_name: string
  item_id: string
  item_code: string
  item_description: string
  unit: string
  quantity_on_hand: number | string
  quantity_reserved: number | string
  quantity_available: number | string
}

export interface StockBalanceResponse {
  total_count: number
  items: StockBalanceItem[]
}

export interface ReconciliationDiscrepancy {
  warehouse_id: string
  item_id: string
  warehouse_name: string
  item_code: string
  balance_qty: number | string
  ledger_qty: number | string
  discrepancy: number | string
}

