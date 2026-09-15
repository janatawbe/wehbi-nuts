import { Link } from 'react-router-dom'
import { useLanguage } from '../../i18n/LanguageContext'
import { localizedField } from '../../i18n/translations'
import type { StorefrontProduct } from '../../types/storefront'
import { getSellingInfo } from './productPricing'
import { ProductImage } from './ProductImage'

interface ProductCardProps {
  product: StorefrontProduct
}

/** A clean, food-focused product card -- image, name, price/selling unit,
 * nothing else. No SKU, no IDs, no admin/AI metadata; see
 * productPricing.ts for the exact weight-vs-unit price presentation. */
export function ProductCard({ product }: ProductCardProps) {
  const { language, t } = useLanguage()
  const { primary, secondary } = getSellingInfo(product, t)
  const soldOut = product.stock_status === 'out_of_stock'
  const name = localizedField(product.name_en, product.name_ar, language)

  return (
    <Link
      to={`/product/${product.id}`}
      className="group block overflow-hidden rounded-2xl border border-stone-200/70 bg-white transition-shadow hover:shadow-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wehbi-red-600"
    >
      <div className="relative aspect-square overflow-hidden bg-cream-deep">
        <ProductImage
          src={product.image}
          alt={name}
          className="h-full w-full transition-transform duration-300 group-hover:scale-105"
        />
        {soldOut && (
          <span className="absolute start-3 top-3 rounded-full bg-roast-900/85 px-2.5 py-1 text-xs font-medium text-white">
            {t('product.soldOut')}
          </span>
        )}
      </div>
      <div className="space-y-1 p-4">
        <p className="truncate text-base font-semibold text-roast-900">{name}</p>
        <p className="text-sm font-medium text-wehbi-red-700">
          {primary}
          {secondary && <span className="ms-1.5 font-normal text-stone-500">· {secondary}</span>}
        </p>
      </div>
    </Link>
  )
}
