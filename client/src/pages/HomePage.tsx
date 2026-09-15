import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listStorefrontCategories } from '../api/storefront'
import { CategoryTile } from '../components/storefront/CategoryTile'
import { HeroSlideshow } from '../components/storefront/HeroSlideshow'
import { ProductGrid } from '../components/storefront/ProductGrid'
import { StorefrontLinkButton } from '../components/storefront/StorefrontButton'
import { useStorefrontProducts } from '../components/storefront/useStorefrontProducts'
import { useLanguage } from '../i18n/LanguageContext'
import { forwardArrow } from '../i18n/translations'
import type { StorefrontCategory } from '../types/storefront'

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0 },
}

function Hero() {
  const { t, direction } = useLanguage()

  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-wehbi-gold-50 via-cream to-cream">
      <div
        className="pointer-events-none absolute -start-24 -top-24 h-72 w-72 rounded-full bg-wehbi-gold-200/60 blur-3xl"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -end-16 top-32 h-64 w-64 rounded-full bg-wehbi-red-200/50 blur-3xl"
        aria-hidden="true"
      />

      <div className="relative mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:gap-16 lg:py-24">
        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        >
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-wehbi-red-600">{t('hero.eyebrow')}</p>
          <h1 className="mt-4 font-display text-4xl font-semibold leading-[1.1] text-roast-900 sm:text-5xl">
            {t('hero.title.line1')}
            <br />
            <span className="text-5xl italic leading-none text-wehbi-red-600 sm:text-6xl">
              {t('hero.title.line2')}
            </span>
          </h1>
          <p className="mt-6 max-w-md text-base text-stone-600">{t('hero.subtitle')}</p>
          <div className="mt-8">
            <StorefrontLinkButton to="/shop">
              {t('hero.cta')}
              <span aria-hidden="true">{forwardArrow(direction)}</span>
            </StorefrontLinkButton>
          </div>
        </motion.div>

        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          transition={{ duration: 0.6, ease: 'easeOut', delay: 0.15 }}
        >
          <HeroSlideshow />
        </motion.div>
      </div>
    </section>
  )
}

function ShopByCategory() {
  const { t } = useLanguage()
  const [categories, setCategories] = useState<StorefrontCategory[]>([])

  useEffect(() => {
    listStorefrontCategories()
      .then(setCategories)
      .catch(() => setCategories([]))
  }, [])

  if (categories.length === 0) return null

  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <div className="text-center">
        <h2 className="font-display text-2xl font-semibold text-roast-900 sm:text-3xl">{t('category.heading')}</h2>
        <p className="mt-2 text-sm text-stone-500">{t('category.subheading')}</p>
      </div>
      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.3 }}
        transition={{ staggerChildren: 0.05 }}
        className="mt-10 grid grid-cols-3 gap-x-4 gap-y-8 sm:grid-cols-4 lg:grid-cols-7"
      >
        {categories.map((category) => (
          <motion.div key={category.id} variants={fadeUp} transition={{ duration: 0.35 }}>
            <CategoryTile category={category} />
          </motion.div>
        ))}
      </motion.div>
    </section>
  )
}

function FeaturedProducts() {
  const { t, direction } = useLanguage()
  const { products, loading, error } = useStorefrontProducts({ limit: 4 })

  if (!loading && !error && products.length === 0) return null

  return (
    <section className="bg-cream-deep py-16">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="font-display text-2xl font-semibold text-roast-900 sm:text-3xl">{t('featured.heading')}</h2>
            <p className="mt-2 text-sm text-stone-500">{t('featured.subheading')}</p>
          </div>
          <Link to="/shop" className="hidden shrink-0 text-sm font-medium text-wehbi-red-700 hover:underline sm:block">
            {t('featured.viewAll')} {forwardArrow(direction)}
          </Link>
        </div>
        <div className="mt-8">
          <ProductGrid products={products} loading={loading} error={error} />
        </div>
      </div>
    </section>
  )
}

function GiftingSpotlight() {
  const { t } = useLanguage()

  return (
    <section className="bg-wehbi-red-600 py-14">
      <div className="mx-auto max-w-4xl px-4 text-center sm:px-6">
        <h2 className="font-display text-2xl font-semibold text-white sm:text-3xl">{t('gifting.heading')}</h2>
        <p className="mx-auto mt-3 max-w-md text-sm text-wehbi-red-50">{t('gifting.body')}</p>
      </div>
    </section>
  )
}

export function HomePage() {
  return (
    <div>
      <Hero />
      <ShopByCategory />
      <FeaturedProducts />
      <GiftingSpotlight />
    </div>
  )
}
