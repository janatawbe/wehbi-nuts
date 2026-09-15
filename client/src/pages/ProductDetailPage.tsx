import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { StorefrontApiError, getStorefrontProduct } from '../api/storefront'
import { AddToCartControl } from '../components/storefront/AddToCartControl'
import { ProductImage } from '../components/storefront/ProductImage'
import { getSellingInfo } from '../components/storefront/productPricing'
import { useLanguage } from '../i18n/LanguageContext'
import { forwardArrow, localizedField, type TranslationKey } from '../i18n/translations'
import type { StorefrontProduct } from '../types/storefront'

const STOCK_LABEL_KEY: Record<StorefrontProduct['stock_status'], TranslationKey | null> = {
  in_stock: null,
  low_stock: 'product.stock.low',
  out_of_stock: 'product.stock.out',
}

const STOCK_DOT_CLASS: Record<StorefrontProduct['stock_status'], string> = {
  in_stock: '',
  low_stock: 'bg-wehbi-gold-500',
  out_of_stock: 'bg-stone-400',
}

const STOCK_LABEL_CLASS: Record<StorefrontProduct['stock_status'], string> = {
  in_stock: '',
  low_stock: 'bg-wehbi-gold-100 text-wehbi-gold-800',
  out_of_stock: 'bg-stone-200 text-stone-600',
}

export function ProductDetailPage() {
  const { language, direction, t } = useLanguage()
  const { id = '' } = useParams<{ id: string }>()
  const [product, setProduct] = useState<StorefrontProduct | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getStorefrontProduct(id)
      .then((data) => {
        if (!cancelled) setProduct(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof StorefrontApiError ? err.message : t('product.loadError'))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- see
    // useStorefrontProducts for why `t`/language changes shouldn't
    // themselves re-trigger a refetch.
  }, [id])

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6" data-testid="product-detail-loading">
        <div className="grid gap-8 sm:grid-cols-2 sm:gap-14">
          <div className="aspect-square animate-pulse rounded-3xl bg-stone-200/70" />
          <div className="space-y-3">
            <div className="h-7 w-2/3 animate-pulse rounded bg-stone-200/70" />
            <div className="h-5 w-1/3 animate-pulse rounded bg-stone-200/70" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !product) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-16 text-center sm:px-6">
        <p className="font-display text-2xl font-semibold text-roast-900">{t('product.notFound.title')}</p>
        <p className="mt-2 text-sm text-stone-500">{error ?? t('product.notFound.body')}</p>
        <Link to="/shop" className="mt-6 inline-block text-sm font-medium text-wehbi-red-700 hover:underline">
          {t('category.browseShop')} {forwardArrow(direction)}
        </Link>
      </div>
    )
  }

  const { primary, secondary } = getSellingInfo(product, t)
  const stockLabelKey = STOCK_LABEL_KEY[product.stock_status]
  const categoryName = product.category ? localizedField(product.category.name_en, product.category.name_ar, language) : null
  const primaryName = localizedField(product.name_en, product.name_ar, language)
  // The OTHER language's name, shown as a secondary line -- a small
  // bilingual touch preserved from the original (English-only) design,
  // just with primary/secondary swapped to match the active language.
  const secondaryName = language === 'ar' ? product.name_en : product.name_ar

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <nav className="mb-6 flex items-center gap-2 text-sm text-stone-400 sm:mb-10" aria-label="Breadcrumb">
        <Link to="/shop" className="transition-colors hover:text-wehbi-red-700">
          {t('product.breadcrumb.shop')}
        </Link>
        {product.category && (
          <>
            <span aria-hidden="true" className="text-stone-300">
              {forwardArrow(direction) === '→' ? '›' : '‹'}
            </span>
            <Link to={`/category/${product.category.slug}`} className="transition-colors hover:text-wehbi-red-700">
              {categoryName}
            </Link>
          </>
        )}
      </nav>

      <div className="grid gap-10 sm:grid-cols-2 sm:gap-14 lg:gap-20">
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className="overflow-hidden rounded-3xl bg-cream-deep shadow-[0_24px_48px_-24px_rgba(44,28,17,0.25)] sm:sticky sm:top-24 sm:self-start"
        >
          <ProductImage src={product.image} alt={primaryName} className="aspect-square w-full" />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut', delay: 0.1 }}
        >
          {categoryName && (
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-wehbi-red-600">{categoryName}</p>
          )}

          <h1 className="mt-2 font-display text-3xl font-semibold leading-tight text-roast-900 sm:text-4xl">
            {primaryName}
          </h1>
          {secondaryName && (
            <p className="mt-1.5 text-base text-stone-400" dir={language === 'ar' ? 'ltr' : 'rtl'}>
              {secondaryName}
            </p>
          )}

          {stockLabelKey && (
            <span
              className={`mt-4 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${STOCK_LABEL_CLASS[product.stock_status]}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${STOCK_DOT_CLASS[product.stock_status]}`} aria-hidden="true" />
              {t(stockLabelKey)}
            </span>
          )}

          <div className="mt-6 flex items-baseline gap-2.5">
            <p className="text-3xl font-semibold text-wehbi-red-700">{primary}</p>
            {product.selling_mode === 'weight' && (
              <span className="text-sm text-stone-400">{t('product.pricePerKg')}</span>
            )}
          </div>
          {secondary && <p className="mt-1 text-sm text-stone-500">{secondary}</p>}

          <div className="mt-7 border-t border-stone-200 pt-7">
            <AddToCartControl product={product} variant="full" />
          </div>

          {product.description_en && (
            <div className="mt-8 border-t border-stone-200 pt-7">
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                {t('product.description.label')}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-stone-600">
                {localizedField(product.description_en, product.description_ar, language)}
              </p>
            </div>
          )}

          {(product.category || product.brand) && (
            <dl className="mt-7 divide-y divide-stone-200 border-t border-stone-200 text-sm">
              {product.category && (
                <div className="flex justify-between py-3">
                  <dt className="text-stone-500">{t('product.category')}</dt>
                  <dd className="font-medium text-roast-900">{categoryName}</dd>
                </div>
              )}
              {product.brand && (
                <div className="flex justify-between py-3">
                  <dt className="text-stone-500">{t('product.brand')}</dt>
                  <dd className="font-medium text-roast-900">{product.brand}</dd>
                </div>
              )}
            </dl>
          )}
        </motion.div>
      </div>
    </div>
  )
}
