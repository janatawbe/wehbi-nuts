export interface StorefrontCategory {
  id: string
  name_en: string
  name_ar: string
  slug: string
}

export type StockStatus = 'in_stock' | 'low_stock' | 'out_of_stock'

export interface StorefrontProduct {
  id: string
  name_en: string
  name_ar: string
  description_en: string | null
  description_ar: string | null
  brand: string | null
  category: StorefrontCategory | null
  selling_mode: 'weight' | 'unit' | null
  package_weight: string | null
  price: string
  stock_status: StockStatus
  image: string | null
}
