import { useEffect, useState } from 'react'
import { StorefrontApiError, listStorefrontProducts } from '../../api/storefront'
import { useLanguage } from '../../i18n/LanguageContext'
import type { StorefrontProduct } from '../../types/storefront'

interface UseStorefrontProductsParams {
  category?: string
  search?: string
  limit?: number
}

interface UseStorefrontProductsResult {
  products: StorefrontProduct[]
  loading: boolean
  error: string | null
}

/** Shared product-fetching used by Shop and Category (and Home's
 * featured-products section) -- one place owning the loading/error
 * lifecycle so every listing behaves identically. */
export function useStorefrontProducts({ category, search, limit }: UseStorefrontProductsParams): UseStorefrontProductsResult {
  const { t } = useLanguage()
  const [products, setProducts] = useState<StorefrontProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    listStorefrontProducts({ category, search, limit })
      .then((data) => {
        if (!cancelled) setProducts(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof StorefrontApiError ? err.message : t('products.loadError'))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `t` changes
    // identity only when `language` changes, which should not itself
    // re-trigger a network refetch; only the actual query params should.
  }, [category, search, limit])

  return { products, loading, error }
}
