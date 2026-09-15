import type { TranslateFn } from '../../i18n/translations'
import type { StorefrontProduct } from '../../types/storefront'

function formatMoney(value: number): string {
  return Number.isInteger(value) ? `$${value}` : `$${value.toFixed(2)}`
}

/** Turns a package weight stored in kilograms (Product.weight, Decimal
 * string) into a shopper-friendly label -- grams under 1kg, kilograms
 * otherwise, matching how a small nuts/coffee shop actually labels
 * packages ("500 g", "1 kg"), not a raw decimal. The unit abbreviation
 * itself is translated (see i18n/translations.ts's 'unit.g'/'unit.kg'). */
function formatPackageWeight(weightKg: string, t: TranslateFn): string {
  const kg = Number(weightKg)
  if (kg < 1) return `${Math.round(kg * 1000)} ${t('unit.g')}`
  return `${Number.isInteger(kg) ? kg.toFixed(0) : kg} ${t('unit.kg')}`
}

export interface SellingInfo {
  /** The headline price string, e.g. "$20 / kg" or "$5.00". */
  primary: string
  /** An optional second line -- package size for a unit-mode product. */
  secondary: string | null
}

/** The one place that turns a Product's price/selling_mode/package_weight
 * into the two short lines a shopper actually needs -- see the Milestone
 * 9 product-card spec: a WEIGHT product shows a per-kilogram price, a
 * UNIT product shows its fixed price plus package size when known. Never
 * shows SKU/IDs/internal fields -- those never even reach this function.
 * `t` is the active-language translator (see i18n/LanguageContext) --
 * every caller passes it via `useLanguage()`, so this stays in step with
 * whichever language the storefront is currently showing. */
export function getSellingInfo(product: StorefrontProduct, t: TranslateFn): SellingInfo {
  const price = Number(product.price)

  if (product.selling_mode === 'weight') {
    return { primary: `${formatMoney(price)} / ${t('unit.kg')}`, secondary: null }
  }

  // Unit-mode products always show two decimals (a normal price tag),
  // unlike the per-kilogram weight price above which drops a bare ".00".
  return {
    primary: `$${price.toFixed(2)}`,
    secondary: product.package_weight
      ? `${formatPackageWeight(product.package_weight, t)} ${t('product.package')}`
      : null,
  }
}
