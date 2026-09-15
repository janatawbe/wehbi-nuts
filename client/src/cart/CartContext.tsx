import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { clearCartStorage, readCartFromStorage, writeCartToStorage } from './cartStorage'
import { DEFAULT_WEIGHT_GRAMS, MAX_UNIT_QUANTITY, WEIGHT_STEP_GRAMS, type AddToCartInput, type CartItem } from './cartTypes'

interface CartContextValue {
  items: CartItem[]
  /** Number of distinct product lines in the cart (not a sum of
   * quantities/weights, which can't be meaningfully added together
   * across selling modes) -- this is what the header badge shows. */
  itemCount: number
  /** Display-only estimate computed from each line's price snapshot.
   * NEVER the authoritative total -- see CheckoutPage, which always
   * shows/uses the server-computed total from the checkout response. */
  subtotal: number
  addItem: (input: AddToCartInput) => void
  removeItem: (productId: string) => void
  increaseQuantity: (productId: string) => void
  decreaseQuantity: (productId: string) => void
  setWeightGrams: (productId: string, grams: number) => void
  clearCart: () => void
}

const DEFAULT_CONTEXT_VALUE: CartContextValue = {
  items: [],
  itemCount: 0,
  subtotal: 0,
  addItem: () => {},
  removeItem: () => {},
  increaseQuantity: () => {},
  decreaseQuantity: () => {},
  setWeightGrams: () => {},
  clearCart: () => {},
}

const CartContext = createContext<CartContextValue>(DEFAULT_CONTEXT_VALUE)

function clampQuantity(value: number): number {
  return Math.min(MAX_UNIT_QUANTITY, Math.max(1, Math.round(value)))
}

/** No upper bound and no minimum beyond "positive" -- see cartTypes.ts
 * and server/app/schemas/checkout.py, which only rejects zero/negative
 * plus an unrelated DB-column-overflow safety bound far beyond any real
 * order. Only guards against something non-finite/non-positive ever
 * reaching cart state (e.g. a corrupted localStorage value) by falling
 * back to the sensible default -- WeightAmountPicker's own parsing is
 * what actually keeps a customer from typing an invalid amount in the
 * first place. */
function clampWeightGrams(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return DEFAULT_WEIGHT_GRAMS
  return Math.round(value)
}

interface CartProviderProps {
  children: ReactNode
}

/** The single source of truth for the customer's shopping cart --
 * persisted to localStorage (see cartStorage.ts) so it survives a
 * refresh/reopen, exactly one line per product (never a duplicate entry
 * for the same product_id -- see addItem). Deliberately never stores
 * customer/checkout information (name, phone, address); those live only
 * in CheckoutPage's own local component state. Never mounted under the
 * admin route tree -- see App.tsx. */
export function CartProvider({ children }: CartProviderProps) {
  const [items, setItems] = useState<CartItem[]>(() => readCartFromStorage())

  useEffect(() => {
    writeCartToStorage(items)
  }, [items])

  const addItem = useCallback((input: AddToCartInput) => {
    setItems((prev) => {
      const existingIndex = prev.findIndex((item) => item.productId === input.productId)

      if (existingIndex === -1) {
        const newItem: CartItem =
          input.sellingMode === 'weight'
            ? {
                productId: input.productId,
                nameEn: input.nameEn,
                nameAr: input.nameAr,
                image: input.image,
                sellingMode: 'weight',
                unitPriceSnapshot: input.unitPriceSnapshot,
                packageWeightSnapshot: null,
                quantity: null,
                weightGrams: clampWeightGrams(input.weightGrams ?? DEFAULT_WEIGHT_GRAMS),
              }
            : {
                productId: input.productId,
                nameEn: input.nameEn,
                nameAr: input.nameAr,
                image: input.image,
                sellingMode: 'unit',
                unitPriceSnapshot: input.unitPriceSnapshot,
                packageWeightSnapshot: input.packageWeightSnapshot,
                quantity: clampQuantity(input.quantity ?? 1),
                weightGrams: null,
              }
        return [...prev, newItem]
      }

      const next = [...prev]
      const existing = next[existingIndex]
      next[existingIndex] =
        existing.sellingMode === 'weight'
          ? { ...existing, weightGrams: clampWeightGrams((existing.weightGrams ?? 0) + WEIGHT_STEP_GRAMS) }
          : { ...existing, quantity: clampQuantity((existing.quantity ?? 0) + (input.quantity ?? 1)) }
      return next
    })
  }, [])

  const removeItem = useCallback((productId: string) => {
    setItems((prev) => prev.filter((item) => item.productId !== productId))
  }, [])

  const increaseQuantity = useCallback((productId: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.productId === productId && item.sellingMode === 'unit'
          ? { ...item, quantity: clampQuantity((item.quantity ?? 0) + 1) }
          : item,
      ),
    )
  }, [])

  const decreaseQuantity = useCallback((productId: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.productId === productId && item.sellingMode === 'unit'
          ? { ...item, quantity: clampQuantity((item.quantity ?? 1) - 1) }
          : item,
      ),
    )
  }, [])

  const setWeightGrams = useCallback((productId: string, grams: number) => {
    setItems((prev) =>
      prev.map((item) =>
        item.productId === productId && item.sellingMode === 'weight'
          ? { ...item, weightGrams: clampWeightGrams(grams) }
          : item,
      ),
    )
  }, [])

  const clearCart = useCallback(() => {
    setItems([])
    clearCartStorage()
  }, [])

  const itemCount = items.length
  const subtotal = useMemo(
    () =>
      items.reduce((sum, item) => {
        const price = Number(item.unitPriceSnapshot)
        const lineQuantity = item.sellingMode === 'weight' ? (item.weightGrams ?? 0) / 1000 : (item.quantity ?? 0)
        return sum + price * lineQuantity
      }, 0),
    [items],
  )

  const value = useMemo<CartContextValue>(
    () => ({
      items,
      itemCount,
      subtotal,
      addItem,
      removeItem,
      increaseQuantity,
      decreaseQuantity,
      setWeightGrams,
      clearCart,
    }),
    [items, itemCount, subtotal, addItem, removeItem, increaseQuantity, decreaseQuantity, setWeightGrams, clearCart],
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart(): CartContextValue {
  return useContext(CartContext)
}
