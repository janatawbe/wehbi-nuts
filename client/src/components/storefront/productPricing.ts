import type { TranslateFn } from '../../i18n/translations'
import type { StorefrontProduct } from '../../types/storefront'

/** Shared "$X" / "$X.XX" money formatting, used for a per-kilogram or
 * per-package PRICE TAG (e.g. "$20 / kg") -- drops a bare ".00" for a
 * whole-dollar price, matching how a small shop actually prices things. */
export function formatMoney(value: number): string {
  return Number.isInteger(value) ? `$${value}` : `$${value.toFixed(2)}`
}

/** Always-two-decimals money formatting ("$6.00", "$16.00") -- used for
 * an actual charged AMOUNT (a cart line subtotal, the order total) rather
 * than a per-unit price tag, matching ordinary checkout/receipt
 * conventions where a whole-dollar total is still shown as "$16.00", not
 * "$16". See client/src/pages/CartPage.tsx, CheckoutPage.tsx, and
 * OrderSuccessPage.tsx. */
export function formatMoneyFixed(value: number): string {
  return `$${value.toFixed(2)}`
}

/** Turns a weight in GRAMS into a shopper-friendly label -- grams under
 * 1000, kilograms otherwise ("300 g", "1 kg"), matching how a small
 * nuts/coffee shop actually labels amounts. Used by the Milestone 10
 * weight-preset picker (client/src/cart), which already works in grams
 * internally -- see formatPackageWeight below for the kilogram-string
 * (Product.weight) equivalent used elsewhere. The unit abbreviation
 * itself is translated (see i18n/translations.ts's 'unit.g'/'unit.kg'). */
export function formatWeightGrams(grams: number, t: TranslateFn): string {
  if (grams < 1000) return `${grams} ${t('unit.g')}`
  const kg = grams / 1000
  return `${Number.isInteger(kg) ? kg.toFixed(0) : kg} ${t('unit.kg')}`
}

/** Turns a package weight stored in kilograms (Product.weight, Decimal
 * string) into a shopper-friendly label -- grams under 1kg, kilograms
 * otherwise, matching how a small nuts/coffee shop actually labels
 * packages ("500 g", "1 kg"), not a raw decimal. The unit abbreviation
 * itself is translated (see i18n/translations.ts's 'unit.g'/'unit.kg'). */
export function formatPackageWeight(weightKg: string, t: TranslateFn): string {
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
