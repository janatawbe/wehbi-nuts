import { motion } from 'framer-motion'
import { useState } from 'react'
import { QUICK_WEIGHT_GRAMS } from '../../cart/cartTypes'
import type { TranslateFn } from '../../i18n/translations'
import { formatWeightGrams } from './productPricing'

type WeightUnit = 'g' | 'kg'

interface WeightAmountPickerProps {
  /** The current committed weight, in grams -- used only to seed the
   * picker's initial display; every subsequent change originates from
   * this component itself (typing, switching units, a quick pick), so it
   * never needs to re-sync from this prop after mount. */
  grams: number
  /** Called with a normalized, whole-gram, strictly-positive value --
   * this is the ONLY shape of value this component ever reports. */
  onChange: (grams: number) => void
  /** Optional: whether the box's current text currently represents a
   * valid weight (a customer mid-typing "1." or having cleared the box
   * is invalid until they finish) -- callers that gate an action (e.g.
   * disabling "Add to Cart") on this can pass a callback. */
  onValidityChange?: (valid: boolean) => void
  disabled?: boolean
  t: TranslateFn
  /** 'md' (default, product page) or 'sm' -- a touch more compact so this
   * still comfortably fits a narrow cart row. */
  size?: 'sm' | 'md'
}

function preferredUnitFor(grams: number): WeightUnit {
  return grams >= 1000 ? 'kg' : 'g'
}

/** Renders `grams` as the number a customer would naturally type for the
 * given unit -- "1.5" for 1500 g in kg mode, "300" for 300 g in g mode.
 * Trims a trailing ".000"-style tail from the kg division without ever
 * rounding away real precision (e.g. 1250 g -> "1.25", not "1.3"). */
function displayAmountFor(grams: number, unit: WeightUnit): string {
  if (unit === 'g') return String(grams)
  const kg = grams / 1000
  return Number.isInteger(kg) ? String(kg) : String(Number(kg.toFixed(3)))
}

/** Parses a customer's typed amount + selected unit into a normalized,
 * whole-gram integer -- or null when the text doesn't represent a
 * strictly-positive weight (empty, non-numeric, zero, negative, or a
 * sub-half-gram amount that would round down to zero). This is the one
 * place "normalize before sending to the backend" actually happens on
 * the frontend; the backend independently re-validates regardless. */
function parseToGrams(amountText: string, unit: WeightUnit): number | null {
  const trimmed = amountText.trim()
  if (!trimmed) return null
  const parsed = Number(trimmed)
  if (!Number.isFinite(parsed) || parsed <= 0) return null
  const rawGrams = unit === 'kg' ? parsed * 1000 : parsed
  const rounded = Math.round(rawGrams)
  return rounded > 0 ? rounded : null
}

/** A direct weight entry -- [amount input] [g / kg toggle] -- plus a
 * handful of one-tap quick amounts underneath. Deliberately NOT a +/-
 * stepper: reaching 3 kg by repeatedly pressing a button was exactly the
 * problem this replaces. Supports decimal kilograms ("1.5"), any
 * positive amount with no fixed maximum, and always reports a normalized
 * whole-gram integer upward. Grams/kilograms only, never "oz". */
export function WeightAmountPicker({
  grams,
  onChange,
  onValidityChange,
  disabled,
  t,
  size = 'md',
}: WeightAmountPickerProps) {
  const [unit, setUnit] = useState<WeightUnit>(() => preferredUnitFor(grams))
  const [amountText, setAmountText] = useState<string>(() => displayAmountFor(grams, preferredUnitFor(grams)))
  const [invalid, setInvalid] = useState(false)

  const commit = (text: string, nextUnit: WeightUnit) => {
    const parsed = parseToGrams(text, nextUnit)
    if (parsed === null) {
      setInvalid(true)
      onValidityChange?.(false)
      return
    }
    setInvalid(false)
    onValidityChange?.(true)
    onChange(parsed)
  }

  const handleAmountChange = (text: string) => {
    setAmountText(text)
    commit(text, unit)
  }

  const handleUnitChange = (nextUnit: WeightUnit) => {
    setUnit(nextUnit)
    commit(amountText, nextUnit)
  }

  const handleQuickPick = (quickGrams: number) => {
    const nextUnit = preferredUnitFor(quickGrams)
    setUnit(nextUnit)
    setAmountText(displayAmountFor(quickGrams, nextUnit))
    setInvalid(false)
    onValidityChange?.(true)
    onChange(quickGrams)
  }

  const fieldPadding = size === 'sm' ? 'py-1.5' : 'py-2.5'
  const fieldText = size === 'sm' ? 'text-xs' : 'text-sm'
  const chipPadding = size === 'sm' ? 'px-2.5 py-1' : 'px-3 py-1.5'

  return (
    <div className="space-y-2">
      <div className="flex items-stretch gap-2">
        <input
          type="number"
          inputMode="decimal"
          step="any"
          min="0"
          value={amountText}
          disabled={disabled}
          onChange={(event) => handleAmountChange(event.target.value)}
          aria-label={t('product.weight.label')}
          aria-invalid={invalid}
          className={`w-24 rounded-full border bg-white px-4 ${fieldPadding} ${fieldText} font-medium text-roast-900 shadow-[0_1px_3px_rgba(44,28,17,0.06)] transition-colors focus:outline-none focus:ring-4 focus:ring-wehbi-red-100 disabled:cursor-not-allowed disabled:bg-stone-100 ${
            invalid ? 'border-wehbi-red-300 focus:border-wehbi-red-500' : 'border-stone-300 focus:border-wehbi-red-400'
          }`}
        />

        <div
          role="group"
          aria-label={t('product.weight.unit.label')}
          className="inline-flex items-center gap-0.5 rounded-full border border-stone-300 bg-white p-1"
        >
          {(['g', 'kg'] as const).map((option) => (
            <button
              key={option}
              type="button"
              disabled={disabled}
              aria-pressed={unit === option}
              onClick={() => handleUnitChange(option)}
              className={`rounded-full font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${chipPadding} ${fieldText} ${
                unit === option ? 'bg-wehbi-red-600 text-white' : 'text-roast-700 hover:bg-cream-deep'
              }`}
            >
              {t(option === 'g' ? 'unit.g' : 'unit.kg')}
            </button>
          ))}
        </div>
      </div>

      {invalid && (
        <p role="alert" className="text-xs text-wehbi-red-700">
          {t('product.weight.invalid')}
        </p>
      )}

      <div className="flex flex-wrap gap-1.5">
        {QUICK_WEIGHT_GRAMS.map((quickGrams) => (
          <motion.button
            key={quickGrams}
            type="button"
            whileTap={disabled ? undefined : { scale: 0.94 }}
            disabled={disabled}
            onClick={() => handleQuickPick(quickGrams)}
            className={`rounded-full bg-cream-deep font-medium text-roast-700 transition-colors hover:bg-stone-200 disabled:cursor-not-allowed disabled:opacity-50 ${chipPadding} ${fieldText}`}
          >
            {formatWeightGrams(quickGrams, t)}
          </motion.button>
        ))}
      </div>
    </div>
  )
}
