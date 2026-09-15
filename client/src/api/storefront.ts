import { API_BASE_URL } from '../config/api'
import type { StorefrontCategory, StorefrontProduct } from '../types/storefront'

export class StorefrontApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'StorefrontApiError'
    this.status = status
  }
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json()
    if (
      data &&
      typeof data === 'object' &&
      'detail' in data &&
      typeof (data as { detail: unknown }).detail === 'string'
    ) {
      return (data as { detail: string }).detail
    }
  } catch {
    // Response body wasn't JSON; fall through to the generic message.
  }
  return `Request failed with status ${response.status}.`
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new StorefrontApiError(await parseErrorMessage(response), response.status)
  }
  return (await response.json()) as T
}

export function listStorefrontCategories(): Promise<StorefrontCategory[]> {
  return getJson<StorefrontCategory[]>('/api/storefront/categories')
}

export interface ListStorefrontProductsParams {
  category?: string
  search?: string
  limit?: number
}

export function listStorefrontProducts(params: ListStorefrontProductsParams = {}): Promise<StorefrontProduct[]> {
  const query = new URLSearchParams()
  if (params.category) query.set('category', params.category)
  if (params.search) query.set('search', params.search)
  if (params.limit) query.set('limit', String(params.limit))
  const queryString = query.toString()
  return getJson<StorefrontProduct[]>(`/api/storefront/products${queryString ? `?${queryString}` : ''}`)
}

export function getStorefrontProduct(id: string): Promise<StorefrontProduct> {
  return getJson<StorefrontProduct>(`/api/storefront/products/${id}`)
}

/** Builds a displayable URL for a Product's stored image path (already a
 * server-relative path like `/api/digitizer/jobs/.../media/refined/x.jpg`
 * -- the same convention every other media reference in this app uses). */
export function getStorefrontImageUrl(imagePath: string): string {
  return `${API_BASE_URL}${imagePath}`
}
