/** Milestone 10: shapes for POST /api/storefront/checkout. Mirrors
 * server/app/schemas/checkout.py exactly -- deliberately carries no price
 * field anywhere in the request; every price in CheckoutResult is
 * computed server-side, never trusted from local cart state. */

export interface CheckoutItemRequest {
  product_id: string
  selling_mode: 'weight' | 'unit'
  weight_grams?: number
  quantity?: number
}

export interface CheckoutRequest {
  customer_name: string
  customer_phone: string
  delivery_address: string
  delivery_area: string
  notes?: string | null
  items: CheckoutItemRequest[]
}

export interface CheckoutItemResult {
  product_id: string | null
  product_name: string
  product_name_ar: string | null
  selling_mode: string
  quantity: string
  unit_price: string
  line_total: string
  package_weight: string | null
}

export interface CheckoutResult {
  id: string
  order_number: string
  status: string
  subtotal: string
  total: string
  items: CheckoutItemResult[]
}
