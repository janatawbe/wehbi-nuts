import { useCallback, useEffect, useMemo, useState } from 'react'
import { DigitizerApiError, listAllDigitizedProducts, listCategories } from '../api/digitizer'
import { ReviewFilterTabs, matchesFilter, type ReviewFilter } from '../components/review/ReviewFilterTabs'
import { ReviewProductList } from '../components/review/ReviewProductList'
import { ReviewProductDetail } from '../components/review/ReviewProductDetail'
import type { Category, DigitizedProduct } from '../types/digitizer'

export function ReviewPage() {
  const [products, setProducts] = useState<DigitizedProduct[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [filter, setFilter] = useState<ReviewFilter>('needs_review')
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [productList, categoryList] = await Promise.all([
        listAllDigitizedProducts(),
        listCategories(),
      ])
      setProducts(productList)
      setCategories(categoryList)
    } catch (err) {
      setError(err instanceof DigitizerApiError ? err.message : 'Could not load products for review.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const filteredProducts = useMemo(
    () => products.filter((p) => matchesFilter(p, filter)),
    [products, filter],
  )

  const selectedProduct = useMemo(
    () => products.find((p) => p.id === selectedProductId) ?? null,
    [products, selectedProductId],
  )

  const handleProductUpdated = (updated: DigitizedProduct) => {
    setProducts((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
  }

  const noProductsYet = !loading && products.length === 0

  return (
    <div className="min-h-dvh bg-cream px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-5xl">
        <h1 className="text-xl font-semibold text-stone-900">Review</h1>

        {error && (
          <p className="mt-3 text-sm text-red-600" data-testid="review-page-error">
            {error}
          </p>
        )}

        {loading ? (
          <p className="mt-6 text-sm text-stone-500">Loading...</p>
        ) : noProductsYet ? (
          <p className="mt-6 text-sm text-stone-500">Nothing to review yet.</p>
        ) : (
          <div className="mt-5">
            <ReviewFilterTabs active={filter} onChange={setFilter} />

            <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div className="min-w-0">
                {filteredProducts.length === 0 ? (
                  <p className="py-6 text-center text-sm text-stone-500">Nothing here.</p>
                ) : (
                  <ReviewProductList
                    products={filteredProducts}
                    filter={filter}
                    selectedProductId={selectedProductId}
                    onSelectProduct={setSelectedProductId}
                  />
                )}
              </div>
              <div className="min-w-0 border-t border-stone-200 pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
                {selectedProduct ? (
                  <ReviewProductDetail
                    product={selectedProduct}
                    allProducts={products}
                    categories={categories}
                    onProductUpdated={handleProductUpdated}
                    onNeedsFullRefresh={refresh}
                    onSelectProduct={setSelectedProductId}
                  />
                ) : (
                  <p className="text-sm text-stone-500">Select a product to review.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
