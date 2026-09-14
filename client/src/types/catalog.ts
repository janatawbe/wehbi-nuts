export type CatalogImportRowAction = 'new' | 'update' | 'unchanged' | 'invalid'

export interface CatalogImportFieldChange {
  field: string
  label: string
  old: string | null
  new: string | null
}

export interface CatalogImportRow {
  row_number: number
  action: CatalogImportRowAction
  product_id: string | null
  sku: string | null
  name_en: string | null
  errors: string[]
  changes: CatalogImportFieldChange[]
}

export interface CatalogImportPreview {
  filename: string
  total_rows: number
  new_count: number
  update_count: number
  unchanged_count: number
  invalid_count: number
  rows: CatalogImportRow[]
}

export interface CatalogImportRowResult {
  row_number: number
  sku: string | null
  name_en: string | null
  errors: string[]
}

export interface CatalogImportResult {
  created: number
  updated: number
  unchanged: number
  failed: number
  failures: CatalogImportRowResult[]
}
