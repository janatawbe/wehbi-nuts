import { motion } from 'framer-motion'
import { MAX_UNIT_QUANTITY } from '../../cart/cartTypes'
import type { TranslateFn } from '../../i18n/translations'

interface QuantityStepperProps {
  value: number
  onIncrease: () => void
  onDecrease: () => void
  disabled?: boolean
  t: TranslateFn
  size?: 'sm' | 'md'
}

/** A deliberately-designed -/count/+ control for a unit-mode product --
 * shared by AddToCartControl's full variant and CartPage's line editor,
 * so a customer sees the exact same tactile stepper before and after
 * adding something to the cart. `size="sm"` is a touch more compact for
 * a cart row; `size="md"` (default) suits the product page. */
export function QuantityStepper({ value, onIncrease, onDecrease, disabled, t, size = 'md' }: QuantityStepperProps) {
  const buttonSize = size === 'sm' ? 'h-7 w-7' : 'h-9 w-9'
  const valueWidth = size === 'sm' ? 'w-5' : 'w-8'

  return (
    <div className="inline-flex items-center gap-1 rounded-full bg-cream-deep p-1">
      <motion.button
        type="button"
        whileTap={disabled || value <= 1 ? undefined : { scale: 0.9 }}
        aria-label={t('cart.item.decrease')}
        disabled={disabled || value <= 1}
        onClick={onDecrease}
        className={`flex ${buttonSize} items-center justify-center rounded-full text-roast-800 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:text-stone-300 disabled:hover:bg-transparent`}
      >
        −
      </motion.button>
      <span className={`${valueWidth} text-center text-sm font-semibold text-roast-900`}>{value}</span>
      <motion.button
        type="button"
        whileTap={disabled || value >= MAX_UNIT_QUANTITY ? undefined : { scale: 0.9 }}
        aria-label={t('cart.item.increase')}
        disabled={disabled || value >= MAX_UNIT_QUANTITY}
        onClick={onIncrease}
        className={`flex ${buttonSize} items-center justify-center rounded-full text-roast-800 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:text-stone-300 disabled:hover:bg-transparent`}
      >
        +
      </motion.button>
    </div>
  )
}
