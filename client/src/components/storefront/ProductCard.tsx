import { Link } from 'react-router-dom'
import { useLanguage } from '../../i18n/LanguageContext'
import { localizedField } from '../../i18n/translations'
import type { StorefrontProduct } from '../../types/storefront'
import { AddToCartControl } from './AddToCartControl'
import { getSellingInfo } from './productPricing'
import { ProductImage } from './ProductImage'

interface ProductCardProps {
  product: StorefrontProduct
}

/** A clean, food-focused, editorial product card -- the photograph is the
 * whole point, so there is deliberately no bordered box around it: just
 * soft rounded corners, generous whitespace, and a shadow that only
 * appears on hover to suggest the card lifting slightly. No SKU, no IDs,
 * no admin/AI metadata; see productPricing.ts for the exact weight-vs-
 * unit price presentation.
 *
 * The Add-to-Cart button (AddToCartControl, 'compact' variant) is a
 * SIBLING of the <Link> below, not nested inside it -- a <button> inside
 * an <a> is invalid HTML and behaves inconsistently across browsers/
 * screen readers, so the card is a plain wrapping <div> with the Link
 * covering the image+name+price (the navigable part) and the button
 * living outside it. */
export function ProductCard({ product }: ProductCardProps) {
  const { language, t } = useLanguage()
  const { primary, secondary } = getSellingInfo(product, t)
  const soldOut = product.stock_status === 'out_of_stock'
  const name = localizedField(product.name_en, product.name_ar, language)

  return (
    <div className="group/card">
      <Link
        to={`/product/${product.id}`}
        className="block focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-wehbi-red-600 rounded-2xl"
      >
        <div className="relative aspect-square overflow-hidden rounded-2xl bg-cream-deep shadow-[0_1px_2px_rgba(44,28,17,0.06)] transition-shadow duration-300 group-hover/card:shadow-[0_20px_35px_-16px_rgba(44,28,17,0.3)]">
          <ProductImage
            src={product.image}
            alt={name}
            className="h-full w-full transition-transform duration-500 ease-out group-hover/card:scale-[1.04]"
          />
          {soldOut && (
            <span className="absolute start-3 top-3 rounded-full bg-roast-900/85 px-2.5 py-1 text-[11px] font-medium tracking-wide text-white">
              {t('product.soldOut')}
            </span>
          )}
        </div>
        <div className="mt-3.5 space-y-1">
          <p className="truncate text-[15px] font-medium text-roast-900">{name}</p>
          <p className="text-sm text-wehbi-red-700">
            <span className="font-semibold">{primary}</span>
            {secondary && <span className="ms-1.5 font-normal text-stone-500">· {secondary}</span>}
          </p>
        </div>
      </Link>
      <div className="mt-3">
        <AddToCartControl product={product} variant="compact" />
      </div>
    </div>
  )
}
