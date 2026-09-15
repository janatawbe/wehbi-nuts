import { motion } from 'framer-motion'
import { useLocation } from 'react-router-dom'
import { StorefrontLinkButton } from '../components/storefront/StorefrontButton'
import { formatMoneyFixed } from '../components/storefront/productPricing'
import { useLanguage } from '../i18n/LanguageContext'
import { localizedField } from '../i18n/translations'
import type { CheckoutResult } from '../types/checkout'

function isCheckoutResult(value: unknown): value is CheckoutResult {
  return (
    !!value &&
    typeof value === 'object' &&
    typeof (value as { order_number?: unknown }).order_number === 'string' &&
    Array.isArray((value as { items?: unknown }).items)
  )
}

function BanknoteIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <rect x="2.5" y="6" width="19" height="12" rx="2.5" />
      <circle cx="12" cy="12" r="2.6" />
      <path d="M5.5 9v.01M18.5 15v.01" strokeLinecap="round" />
    </svg>
  )
}

/** A small, on-brand success mark -- two soft brand-colored rings behind
 * a checkmark, not a generic oversized green tick -- so the celebration
 * still reads as "Wehbi Nuts" rather than a stock success icon. */
function SuccessMark() {
  return (
    <div className="relative mx-auto flex h-20 w-20 items-center justify-center">
      <span className="absolute inset-0 rounded-full bg-wehbi-gold-200/60" aria-hidden="true" />
      <span className="absolute inset-2 rounded-full bg-wehbi-red-600" aria-hidden="true" />
      <svg viewBox="0 0 24 24" className="relative h-8 w-8 text-white" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
        <path d="M5 12.5l4.5 4.5L19 7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  )
}

/** Milestone 10: shown right after a successful checkout, reading the
 * confirmed order ONLY from React Router navigation state (set by
 * CheckoutPage's `navigate('/order/success', { state: { result } })`) --
 * deliberately NOT from a public GET /order/:number lookup, which this
 * milestone does not implement. A direct visit or refresh has no
 * navigation state, so it falls back to a graceful "no order to show"
 * state with a way back to the shop, rather than attempting to fetch
 * anything. */
export function OrderSuccessPage() {
  const { language, t } = useLanguage()
  const location = useLocation()
  const state = location.state as { result?: unknown } | null
  const result = isCheckoutResult(state?.result) ? (state!.result as CheckoutResult) : null

  if (!result) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-20 text-center sm:px-6" data-testid="order-success-invalid">
        <h1 className="font-display text-2xl font-semibold text-roast-900">{t('orderSuccess.invalid.title')}</h1>
        <p className="mt-2 text-sm text-stone-500">{t('orderSuccess.invalid.body')}</p>
        <div className="mt-8">
          <StorefrontLinkButton to="/shop">{t('cart.continueShopping')}</StorefrontLinkButton>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center sm:px-6 sm:py-20">
      <motion.div
        initial={{ opacity: 0, scale: 0.7 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: 'spring', stiffness: 260, damping: 18 }}
      >
        <SuccessMark />
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.15 }}>
        <h1 className="mt-6 font-display text-3xl font-semibold text-roast-900">{t('orderSuccess.title')}</h1>
        <p className="mt-2 text-sm text-stone-500">{t('orderSuccess.thankYou')}</p>

        <div className="mt-6 inline-block rounded-2xl bg-cream-deep px-6 py-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{t('orderSuccess.orderNumber')}</p>
          <p className="mt-1 font-display text-2xl font-semibold text-wehbi-red-700">{result.order_number}</p>
        </div>

        <div className="mt-8 rounded-3xl bg-white p-6 text-start shadow-[0_20px_45px_-24px_rgba(44,28,17,0.25)] ring-1 ring-stone-100">
          <h2 className="font-display text-lg font-semibold text-roast-900">{t('order.summary.title')}</h2>
          <ul className="mt-4 divide-y divide-stone-200">
            {result.items.map((item, index) => (
              <li key={index} className="flex justify-between gap-3 py-3 text-sm first:pt-0">
                <span className="text-roast-900">{localizedField(item.product_name, item.product_name_ar, language)}</span>
                <span className="shrink-0 font-medium text-roast-900">{formatMoneyFixed(Number(item.line_total))}</span>
              </li>
            ))}
          </ul>
          <div className="mt-2 flex justify-between border-t border-stone-200 pt-4">
            <span className="font-semibold text-roast-900">{t('cart.orderTotal')}</span>
            <span className="text-xl font-semibold text-wehbi-red-700">{formatMoneyFixed(Number(result.total))}</span>
          </div>
        </div>

        <div className="mt-8 flex items-start gap-3 rounded-2xl bg-cream-deep p-4 text-start">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white text-wehbi-red-600">
            <BanknoteIcon />
          </span>
          <div>
            <p className="font-semibold text-roast-900">{t('checkout.payment.cod')}</p>
            <p className="mt-0.5 text-sm text-stone-500">{t('orderSuccess.codNotice')}</p>
          </div>
        </div>

        <div className="mt-8">
          <StorefrontLinkButton to="/shop">{t('cart.continueShopping')}</StorefrontLinkButton>
        </div>
      </motion.div>
    </div>
  )
}
