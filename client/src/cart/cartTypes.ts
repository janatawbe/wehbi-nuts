/** Milestone 10 cart line. Exactly one product per `productId` in the
 * cart at a time (see CartContext.addItem) -- this is what makes a
 * duplicate cart entry structurally impossible rather than merely
 * discouraged.
 *
 * `unitPriceSnapshot`/`packageWeightSnapshot` exist ONLY to render the
 * cart/checkout summary instantly without refetching the product -- they
 * are display estimates. The one and only authoritative price is
 * computed server-side at checkout from the CURRENT Product row (see
 * api/checkout.ts and server/app/services/checkout_service.py); nothing
 * in this cart is ever sent to, or trusted by, the backend as a price.
 *
 * Exactly one of `quantity`/`weightGrams` is meaningful, selected by
 * `sellingMode` -- mirrors CheckoutItemRequest on the backend. */
export interface CartItem {
  productId: string
  nameEn: string
  nameAr: string
  image: string | null
  sellingMode: 'weight' | 'unit'
  unitPriceSnapshot: string
  packageWeightSnapshot: string | null
  quantity: number | null
  weightGrams: number | null
}

/** Quick-pick weight chips shown under the direct amount input (see
 * WeightAmountPicker) -- NOT an exhaustive/enforced set. A customer can
 * type any positive amount directly (in grams OR kilograms, including
 * decimals like "1.5" kg); these are just the handful of amounts worth
 * one tap. Grams/kilograms only, never "oz". */
export const QUICK_WEIGHT_GRAMS: readonly number[] = [100, 250, 500, 1000]

/** The sensible small default for a brand-new weight-mode cart line
 * (ProductCard's one-click quick-add uses exactly this) -- NOT a
 * validation floor. Direct entry only requires a strictly positive
 * amount (see WeightAmountPicker's own parsing) -- there is deliberately
 * no matching upper bound either (see server/app/schemas/checkout.py,
 * which only rejects zero/negative plus an unrelated DB-column-overflow
 * safety bound far beyond any real order). */
export const DEFAULT_WEIGHT_GRAMS = 100

/** What a repeated "Add to Cart" click adds to an already-in-cart weight
 * line (see CartContext.addItem) -- editing to an exact amount happens
 * in the cart itself via WeightAmountPicker's direct entry. */
export const WEIGHT_STEP_GRAMS = 100

/** A generous sanity cap on a unit-mode line -- must match
 * server/app/schemas/checkout.py's MAX_UNIT_QUANTITY. */
export const MAX_UNIT_QUANTITY = 20

export interface AddToCartInput {
  productId: string
  nameEn: string
  nameAr: string
  image: string | null
  sellingMode: 'weight' | 'unit'
  unitPriceSnapshot: string
  packageWeightSnapshot: string | null
  /** Required (and only meaningful) when sellingMode === 'weight'. */
  weightGrams?: number
  /** Required (and only meaningful) when sellingMode === 'unit'. */
  quantity?: number
}
