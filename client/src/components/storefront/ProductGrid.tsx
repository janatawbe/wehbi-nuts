import { useLanguage } from '../../i18n/LanguageContext'
import type { StorefrontProduct } from '../../types/storefront'
import { ProductCard } from './ProductCard'

interface ProductGridProps {
  products: StorefrontProduct[]
  loading: boolean
  error: string | null
  emptyMessage?: string
}

/** Shared loading/error/empty/grid states for anywhere a product listing
 * is shown (Shop, Category) -- one place so those two pages can't drift
 * into inconsistent behavior. `emptyMessage`, when passed, is already a
 * translated string from the caller (each caller knows its own more
 * specific empty copy); the default here is this component's own,
 * translated internally since it has no caller-supplied message. */
export function ProductGrid({ products, loading, error, emptyMessage }: ProductGridProps) {
  const { t } = useLanguage()
  const resolvedEmptyMessage = emptyMessage ?? t('products.empty')

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4" data-testid="product-grid-loading">
        {Array.from({ length: 8 }).map((_, index) => (
          <div key={index} className="animate-pulse space-y-3">
            <div className="aspect-square rounded-2xl bg-stone-200/70" />
            <div className="h-4 w-3/4 rounded bg-stone-200/70" />
            <div className="h-4 w-1/3 rounded bg-stone-200/70" />
          </div>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <p className="py-16 text-center text-sm text-wehbi-red-700" data-testid="product-grid-error">
        {error}
      </p>
    )
  }

  if (products.length === 0) {
    return (
      <p className="py-16 text-center text-sm text-stone-500" data-testid="product-grid-empty">
        {resolvedEmptyMessage}
      </p>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4" data-testid="product-grid">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  )
}
