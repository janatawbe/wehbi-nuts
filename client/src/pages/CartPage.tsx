import { AnimatePresence, motion } from 'framer-motion'
import { Link, useNavigate } from 'react-router-dom'
import { useCart } from '../cart/CartContext'
import type { CartItem } from '../cart/cartTypes'
import { ProductImage } from '../components/storefront/ProductImage'
import { QuantityStepper } from '../components/storefront/QuantityStepper'
import { StorefrontButton, StorefrontLinkButton } from '../components/storefront/StorefrontButton'
import { WeightAmountPicker } from '../components/storefront/WeightAmountPicker'
import { formatMoney, formatMoneyFixed, formatPackageWeight } from '../components/storefront/productPricing'
import { useLanguage } from '../i18n/LanguageContext'
import { localizedField } from '../i18n/translations'
import type { TranslateFn } from '../i18n/translations'

function lineTotal(item: CartItem): number {
  const price = Number(item.unitPriceSnapshot)
  const quantity = item.sellingMode === 'weight' ? (item.weightGrams ?? 0) / 1000 : (item.quantity ?? 0)
  return price * quantity
}

interface CartLineProps {
  item: CartItem
  t: TranslateFn
}

function CartLine({ item, t }: CartLineProps) {
  const { language } = useLanguage()
  const { removeItem, increaseQuantity, decreaseQuantity, setWeightGrams } = useCart()
  const name = localizedField(item.nameEn, item.nameAr, language)

  return (
    <motion.li
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.2 }}
      className="flex gap-4 py-6 first:pt-0 sm:gap-5"
    >
      <div className="h-24 w-24 shrink-0 overflow-hidden rounded-2xl bg-cream-deep sm:h-28 sm:w-28">
        <ProductImage src={item.image} alt={name} className="h-full w-full" />
      </div>

      <div className="flex flex-1 flex-col justify-between gap-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-medium text-roast-900">{name}</p>
            <p className="mt-0.5 text-sm text-stone-400">
              {item.sellingMode === 'weight' ? (
                <>
                  {formatMoney(Number(item.unitPriceSnapshot))} / {t('unit.kg')}
                </>
              ) : (
                <>
                  {formatMoney(Number(item.unitPriceSnapshot))}
                  {item.packageWeightSnapshot && (
                    <span className="ms-1.5">
                      · {formatPackageWeight(item.packageWeightSnapshot, t)} {t('product.package')}
                    </span>
                  )}
                </>
              )}
            </p>
          </div>
          <p className="shrink-0 font-semibold text-wehbi-red-700">{formatMoneyFixed(lineTotal(item))}</p>
        </div>

        <div className="flex flex-wrap items-start justify-between gap-3">
          {item.sellingMode === 'weight' ? (
            <WeightAmountPicker
              grams={item.weightGrams ?? 100}
              onChange={(grams) => setWeightGrams(item.productId, grams)}
              t={t}
              size="sm"
            />
          ) : (
            <QuantityStepper
              value={item.quantity ?? 1}
              onIncrease={() => increaseQuantity(item.productId)}
              onDecrease={() => decreaseQuantity(item.productId)}
              t={t}
              size="sm"
            />
          )}
          <button
            type="button"
            onClick={() => removeItem(item.productId)}
            className="text-sm text-stone-400 underline-offset-2 transition-colors hover:text-wehbi-red-700 hover:underline"
          >
            {t('cart.item.remove')}
          </button>
        </div>
      </div>
    </motion.li>
  )
}

export function CartPage() {
  const { t } = useLanguage()
  const navigate = useNavigate()
  const { items, subtotal } = useCart()

  if (items.length === 0) {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center sm:px-6">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-cream-deep">
          <svg viewBox="0 0 24 24" className="h-7 w-7 text-wehbi-red-400" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
            <path d="M3 4h2l2.4 12.2a2 2 0 0 0 2 1.6h7.2a2 2 0 0 0 2-1.6L20.5 8H6" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="9.5" cy="20.5" r="1.3" fill="currentColor" stroke="none" />
            <circle cx="17" cy="20.5" r="1.3" fill="currentColor" stroke="none" />
          </svg>
        </div>
        <h1 className="mt-5 font-display text-2xl font-semibold text-roast-900">{t('cart.empty.title')}</h1>
        <p className="mt-2 text-sm text-stone-500">{t('cart.empty.body')}</p>
        <div className="mt-8">
          <StorefrontLinkButton to="/shop">{t('cart.continueShopping')}</StorefrontLinkButton>
        </div>
        <p className="mt-6 text-sm">
          <Link to="/" className="text-wehbi-red-700 hover:underline">
            {t('nav.backHome')}
          </Link>
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-12">
      <h1 className="font-display text-3xl font-semibold text-roast-900">{t('cart.title')}</h1>

      <div className="mt-8 grid gap-10 lg:grid-cols-5 lg:items-start lg:gap-14">
        <div className="lg:col-span-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{t('cart.section.items')}</p>
          <ul className="mt-3 divide-y divide-stone-200">
            <AnimatePresence initial={false}>
              {items.map((item) => (
                <CartLine key={item.productId} item={item} t={t} />
              ))}
            </AnimatePresence>
          </ul>
        </div>

        <div className="lg:col-span-2">
          <div className="rounded-3xl bg-white p-6 shadow-[0_20px_45px_-24px_rgba(44,28,17,0.25)] ring-1 ring-stone-100 lg:sticky lg:top-24">
            <h2 className="font-display text-lg font-semibold text-roast-900">{t('order.summary.title')}</h2>
            <div className="mt-5 flex items-center justify-between border-t border-stone-200 pt-5">
              <span className="font-semibold text-roast-900">{t('cart.orderTotal')}</span>
              <span className="text-xl font-semibold text-wehbi-red-700">{formatMoneyFixed(subtotal)}</span>
            </div>
            <StorefrontButton className="mt-6 w-full" onClick={() => navigate('/checkout')}>
              {t('cart.checkout')}
            </StorefrontButton>
          </div>
        </div>
      </div>
    </div>
  )
}
