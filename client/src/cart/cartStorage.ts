import type { CartItem } from './cartTypes'

const STORAGE_KEY = 'wehbi-nuts-cart'

function isValidCartItem(value: unknown): value is CartItem {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return (
    typeof item.productId === 'string' &&
    typeof item.nameEn === 'string' &&
    typeof item.nameAr === 'string' &&
    (item.image === null || typeof item.image === 'string') &&
    (item.sellingMode === 'weight' || item.sellingMode === 'unit') &&
    typeof item.unitPriceSnapshot === 'string' &&
    (item.packageWeightSnapshot === null || typeof item.packageWeightSnapshot === 'string') &&
    (item.quantity === null || typeof item.quantity === 'number') &&
    (item.weightGrams === null || typeof item.weightGrams === 'number')
  )
}

/** Reads the persisted cart -- NEVER throws, and silently drops anything
 * that doesn't match the expected shape (a stale/corrupted localStorage
 * value degrades to an empty cart rather than crashing the app). Only
 * ever holds CartItem[] -- no customer name/phone/address is ever
 * written here (see CheckoutPage, which keeps that in local component
 * state only). */
export function readCartFromStorage(): CartItem[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isValidCartItem)
  } catch {
    return []
  }
}

export function writeCartToStorage(items: CartItem[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
  } catch {
    // Best-effort only -- a private-browsing/storage-disabled session
    // simply won't persist the cart across reloads.
  }
}

export function clearCartStorage(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Best-effort only.
  }
}
