import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { useCart } from '../../cart/CartContext'
import { DEFAULT_WEIGHT_GRAMS } from '../../cart/cartTypes'
import { useLanguage } from '../../i18n/LanguageContext'
import type { StorefrontProduct } from '../../types/storefront'
import { formatMoneyFixed } from './productPricing'
import { QuantityStepper } from './QuantityStepper'
import { StorefrontButton } from './StorefrontButton'
import { WeightAmountPicker } from './WeightAmountPicker'

interface AddToCartControlProps {
  product: StorefrontProduct
  /** 'compact' (ProductCard, in a grid -- a single one-click Add button
   * using the smallest quick amount/quantity 1) or 'full'
   * (ProductDetailPage -- lets the customer pick the exact weight/
   * quantity before adding). */
  variant?: 'compact' | 'full'
  className?: string
}

const CONFIRMATION_DURATION_MS = 1500

function CheckIcon({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
      <path d="M5 12.5l4.5 4.5L19 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/** Brief, local "added to cart" feedback -- a boolean that flips true on
 * `trigger()` and back to false after CONFIRMATION_DURATION_MS, resetting
 * its own timer on every call so repeated clicks (even before the
 * previous confirmation finished) always keep showing feedback rather
 * than looking like nothing happened. */
function useAddedFeedback() {
  const [justAdded, setJustAdded] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(
    () => () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    },
    [],
  )

  const trigger = () => {
    setJustAdded(true)
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => setJustAdded(false), CONFIRMATION_DURATION_MS)
  }

  return { justAdded, trigger }
}

/** The one Add-to-Cart control used everywhere a product can be added --
 * never exposes internal terms like "selling_mode": a weight product
 * always shows grams/kilograms only (never "oz"), a unit product shows a
 * plain integer stepper. See client/src/cart/CartContext for what
 * actually happens when "Add to Cart" is pressed, and StorefrontHeader
 * for the matching cart-icon pulse this triggers. */
export function AddToCartControl({ product, variant = 'compact', className = '' }: AddToCartControlProps) {
  const { t } = useLanguage()
  const { addItem } = useCart()
  const [selectedGrams, setSelectedGrams] = useState<number>(DEFAULT_WEIGHT_GRAMS)
  const [weightValid, setWeightValid] = useState(true)
  const [selectedQuantity, setSelectedQuantity] = useState<number>(1)
  const { justAdded, trigger } = useAddedFeedback()

  const soldOut = product.stock_status === 'out_of_stock'
  const isWeight = product.selling_mode === 'weight'

  const handleAdd = () => {
    if (soldOut) return
    addItem({
      productId: product.id,
      nameEn: product.name_en,
      nameAr: product.name_ar,
      image: product.image,
      sellingMode: isWeight ? 'weight' : 'unit',
      unitPriceSnapshot: product.price,
      packageWeightSnapshot: product.package_weight,
      weightGrams: isWeight ? selectedGrams : undefined,
      quantity: isWeight ? undefined : selectedQuantity,
    })
    trigger()
  }

  if (variant === 'compact') {
    return (
      <motion.button
        type="button"
        whileTap={soldOut ? undefined : { scale: 0.96 }}
        onClick={(event) => {
          // ProductCard renders this inside the same card as a <Link> to
          // the product's detail page -- this button is a sibling, not
          // nested inside that anchor, but stopPropagation is kept as a
          // defensive guard against any future layout change that would
          // otherwise turn a click here into an unwanted navigation.
          event.preventDefault()
          event.stopPropagation()
          handleAdd()
        }}
        disabled={soldOut}
        aria-live="polite"
        className={`flex w-full items-center justify-center gap-1.5 rounded-full border px-3 py-2 text-xs font-semibold tracking-wide transition-colors disabled:cursor-not-allowed disabled:border-stone-200 disabled:text-stone-400 disabled:hover:bg-transparent ${
          justAdded
            ? 'border-wehbi-gold-500 bg-wehbi-gold-500 text-roast-900'
            : 'border-wehbi-red-600 text-wehbi-red-700 hover:bg-wehbi-red-600 hover:text-white'
        } ${className}`}
      >
        {justAdded ? (
          <>
            <CheckIcon className="h-3.5 w-3.5" />
            {t('product.added')}
          </>
        ) : (
          t('product.addToCart')
        )}
      </motion.button>
    )
  }

  const weightPrice = Number(product.price) * (selectedGrams / 1000)

  return (
    <div className={`relative ${className}`}>
      {isWeight ? (
        <div>
          <span className="mb-2.5 block text-xs font-semibold uppercase tracking-wide text-stone-500">
            {t('product.weight.label')}
          </span>
          <WeightAmountPicker
            grams={selectedGrams}
            onChange={setSelectedGrams}
            onValidityChange={setWeightValid}
            disabled={soldOut}
            t={t}
          />
          {weightValid && (
            <p className="mt-3 text-sm text-stone-500">
              {t('product.weight.priceForAmount')}:{' '}
              <span className="font-semibold text-wehbi-red-700">{formatMoneyFixed(weightPrice)}</span>
            </p>
          )}
        </div>
      ) : (
        <div>
          <span className="mb-2.5 block text-xs font-semibold uppercase tracking-wide text-stone-500">
            {t('product.quantity.label')}
          </span>
          <QuantityStepper
            value={selectedQuantity}
            onIncrease={() => setSelectedQuantity((q) => Math.min(q + 1, 20))}
            onDecrease={() => setSelectedQuantity((q) => Math.max(q - 1, 1))}
            disabled={soldOut}
            t={t}
          />
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <StorefrontButton
          onClick={handleAdd}
          disabled={soldOut || (isWeight && !weightValid)}
          className="w-full sm:w-auto"
        >
          {t('product.addToCart')}
        </StorefrontButton>

        <AnimatePresence>
          {justAdded && (
            <motion.p
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              aria-live="polite"
              className="flex items-center gap-1.5 text-sm font-medium text-wehbi-gold-700"
            >
              <CheckIcon className="h-4 w-4" />
              {t('product.addedToCart')}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
