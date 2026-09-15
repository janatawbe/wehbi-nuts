import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { listStorefrontCategories } from '../api/storefront'
import { ProductGrid } from '../components/storefront/ProductGrid'
import { useStorefrontProducts } from '../components/storefront/useStorefrontProducts'
import { useLanguage } from '../i18n/LanguageContext'
import { forwardArrow, localizedField } from '../i18n/translations'
import type { StorefrontCategory } from '../types/storefront'

export function CategoryPage() {
  const { language, direction, t } = useLanguage()
  const { slug = '' } = useParams<{ slug: string }>()
  const [categories, setCategories] = useState<StorefrontCategory[] | null>(null)

  useEffect(() => {
    listStorefrontCategories()
      .then(setCategories)
      .catch(() => setCategories([]))
  }, [])

  const { products, loading, error } = useStorefrontProducts({ category: slug })

  const category = categories?.find((c) => c.slug === slug)
  const categoryKnown = categories === null || Boolean(category)

  if (categories !== null && !category) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16 text-center sm:px-6">
        <p className="font-display text-2xl font-semibold text-roast-900">{t('category.notFound.title')}</p>
        <p className="mt-2 text-sm text-stone-500">{t('category.notFound.body')}</p>
        <Link to="/shop" className="mt-6 inline-block text-sm font-medium text-wehbi-red-700 hover:underline">
          {t('category.browseShop')} {forwardArrow(direction)}
        </Link>
      </div>
    )
  }

  const categoryName = category ? localizedField(category.name_en, category.name_ar, language) : null

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-3xl font-semibold text-roast-900">
        {categoryName ?? (categoryKnown ? '' : ' ')}
      </h1>
      <div className="mt-8">
        <ProductGrid
          products={products}
          loading={loading || categories === null}
          error={error}
          emptyMessage={t('category.empty')}
        />
      </div>
    </div>
  )
}
