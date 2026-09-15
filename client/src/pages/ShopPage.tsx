import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listStorefrontCategories } from '../api/storefront'
import { ProductGrid } from '../components/storefront/ProductGrid'
import { useStorefrontProducts } from '../components/storefront/useStorefrontProducts'
import { useLanguage } from '../i18n/LanguageContext'
import { localizedField } from '../i18n/translations'
import type { StorefrontCategory } from '../types/storefront'

const CATEGORY_INDICATOR_LAYOUT_ID = 'shop-category-indicator'

/** The full catalog: a compact, typography-led category nav + a grid.
 * Deliberately text-only, not photo tiles -- the homepage's "Shop by
 * Category" already owns the photo-led category language; this row
 * stays compact (a thin underline tab bar, not seven large tiles) so
 * products stay the visual focus of the page they're actually on.
 * Search happens exclusively through the header's search box (which
 * navigates here with a `search` query param, read directly below) -- a
 * second Shop-page search input would just duplicate that. */
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
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-12">
      <div className="max-w-xl">
        <h1 className="font-display text-3xl font-semibold text-roast-900 sm:text-4xl">{t('shop.title')}</h1>
        <p className="mt-2 text-sm text-stone-500">{t('shop.subheading')}</p>
      </div>

      <div
        className="mt-8 -mx-4 flex gap-1 overflow-x-auto border-b border-stone-200 px-4 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0"
        role="tablist"
        aria-label={t('shop.filter.label')}
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeCategory === ''}
          onClick={() => selectCategory('')}
          className={`relative shrink-0 px-3.5 pb-3 pt-1 text-sm font-medium transition-colors sm:text-base ${
            activeCategory === '' ? 'text-wehbi-red-700' : 'text-stone-500 hover:text-roast-800'
          }`}
        >
          {t('shop.filter.all')}
          {activeCategory === '' && (
            <motion.span
              layoutId={CATEGORY_INDICATOR_LAYOUT_ID}
              transition={{ type: 'spring', stiffness: 420, damping: 34 }}
              className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-wehbi-red-600"
            />
          )}
        </button>

        {categories.map((category) => {
          const active = activeCategory === category.slug
          return (
            <button
              key={category.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => selectCategory(category.slug)}
              className={`relative shrink-0 px-3.5 pb-3 pt-1 text-sm font-medium transition-colors sm:text-base ${
                active ? 'text-wehbi-red-700' : 'text-stone-500 hover:text-roast-800'
              }`}
            >
              {localizedField(category.name_en, category.name_ar, language)}
              {active && (
                <motion.span
                  layoutId={CATEGORY_INDICATOR_LAYOUT_ID}
                  transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                  className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-wehbi-red-600"
                />
              )}
            </button>
          )
        })}
      </div>

      <motion.div
        key={`${activeCategory}-${urlSearch}`}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: 'easeOut' }}
        className="mt-10"
      >
        <ProductGrid products={products} loading={loading} error={error} emptyMessage={t('shop.empty')} />
      </motion.div>
    </div>
  )
}
