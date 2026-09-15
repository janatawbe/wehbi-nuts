import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listStorefrontCategories } from '../api/storefront'
import { ProductGrid } from '../components/storefront/ProductGrid'
import { useStorefrontProducts } from '../components/storefront/useStorefrontProducts'
import { useLanguage } from '../i18n/LanguageContext'
import { localizedField } from '../i18n/translations'
import type { StorefrontCategory } from '../types/storefront'

/** The full catalog: category chips + a grid. Search happens exclusively
 * through the header's search box (which navigates here with a `search`
 * query param, read directly below) -- a second Shop-page search input
 * would just duplicate that. Deliberately no sort/facet controls -- the
 * catalog is small enough that filtering by category and a name search
 * cover real shopping needs without turning this into a faceted-search
 * dashboard. */
export function ShopPage() {
  const { language, t } = useLanguage()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeCategory = searchParams.get('category') ?? ''
  const urlSearch = searchParams.get('search') ?? ''
  const [categories, setCategories] = useState<StorefrontCategory[]>([])

  useEffect(() => {
    listStorefrontCategories()
      .then(setCategories)
      .catch(() => setCategories([]))
  }, [])

  const { products, loading, error } = useStorefrontProducts({
    category: activeCategory || undefined,
    search: urlSearch || undefined,
  })

  const selectCategory = (slug: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (slug) next.set('category', slug)
      else next.delete('category')
      return next
    })
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-3xl font-semibold text-roast-900">{t('shop.title')}</h1>

      <div className="mt-6 flex flex-wrap gap-2" role="tablist" aria-label={t('shop.filter.label')}>
        <button
          type="button"
          role="tab"
          aria-selected={activeCategory === ''}
          onClick={() => selectCategory('')}
          className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
            activeCategory === '' ? 'bg-wehbi-red-600 text-white' : 'bg-white text-roast-800 hover:bg-cream-deep'
          }`}
        >
          {t('shop.filter.all')}
        </button>
        {categories.map((category) => (
          <button
            key={category.id}
            type="button"
            role="tab"
            aria-selected={activeCategory === category.slug}
            onClick={() => selectCategory(category.slug)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
              activeCategory === category.slug
                ? 'bg-wehbi-red-600 text-white'
                : 'bg-white text-roast-800 hover:bg-cream-deep'
            }`}
          >
            {localizedField(category.name_en, category.name_ar, language)}
          </button>
        ))}
      </div>

      <div className="mt-8">
        <ProductGrid products={products} loading={loading} error={error} emptyMessage={t('shop.empty')} />
      </div>
    </div>
  )
}
