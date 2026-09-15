import { motion } from 'framer-motion'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { StorefrontApiError } from '../api/storefront'
import { submitCheckout } from '../api/checkout'
import { useCart } from '../cart/CartContext'
import { StorefrontButton, StorefrontLinkButton } from '../components/storefront/StorefrontButton'
import { formatMoneyFixed } from '../components/storefront/productPricing'
import { useLanguage } from '../i18n/LanguageContext'
import { localizedField } from '../i18n/translations'
import type { CheckoutItemRequest, CheckoutRequest } from '../types/checkout'

interface FormState {
  customerName: string
  customerPhone: string
  deliveryAddress: string
  deliveryArea: string
  notes: string
}

const EMPTY_FORM: FormState = {
  customerName: '',
  customerPhone: '',
  deliveryAddress: '',
  deliveryArea: '',
  notes: '',
}

type FieldName = keyof FormState

function BanknoteIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <rect x="2.5" y="6" width="19" height="12" rx="2.5" />
      <circle cx="12" cy="12" r="2.6" />
      <path d="M5.5 9v.01M18.5 15v.01" strokeLinecap="round" />
    </svg>
  )
}

export function CheckoutPage() {
  const { language, t } = useLanguage()
  const navigate = useNavigate()
  const { items, subtotal, clearCart } = useCart()

  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [touched, setTouched] = useState<Partial<Record<FieldName, boolean>>>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  if (items.length === 0) {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center sm:px-6">
        <h1 className="font-display text-2xl font-semibold text-roast-900">{t('cart.empty.title')}</h1>
        <p className="mt-2 text-sm text-stone-500">{t('checkout.emptyCart.body')}</p>
        <div className="mt-8">
          <StorefrontLinkButton to="/shop">{t('cart.continueShopping')}</StorefrontLinkButton>
        </div>
      </div>
    )
  }

  const requiredFields: FieldName[] = ['customerName', 'customerPhone', 'deliveryAddress', 'deliveryArea']
  const fieldErrors: Partial<Record<FieldName, string>> = {}
  for (const field of requiredFields) {
    if (!form[field].trim()) {
      fieldErrors[field] = t('checkout.validation.required')
    }
  }
  const isValid = Object.keys(fieldErrors).length === 0

  const updateField = (field: FieldName) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  const markTouched = (field: FieldName) => () => {
    setTouched((prev) => ({ ...prev, [field]: true }))
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setTouched({ customerName: true, customerPhone: true, deliveryAddress: true, deliveryArea: true })
    setSubmitError(null)

    if (!isValid) return

    const checkoutItems: CheckoutItemRequest[] = items.map((item) =>
      item.sellingMode === 'weight'
        ? { product_id: item.productId, selling_mode: 'weight', weight_grams: item.weightGrams ?? undefined }
        : { product_id: item.productId, selling_mode: 'unit', quantity: item.quantity ?? undefined },
    )

    const request: CheckoutRequest = {
      customer_name: form.customerName.trim(),
      customer_phone: form.customerPhone.trim(),
      delivery_address: form.deliveryAddress.trim(),
      delivery_area: form.deliveryArea.trim(),
      notes: form.notes.trim() || null,
      items: checkoutItems,
    }

    setSubmitting(true)
    try {
      const result = await submitCheckout(request)
      // Cart is cleared ONLY after the backend has confirmed the order
      // was actually created -- a failed/errored request below leaves it
      // completely untouched.
      clearCart()
      navigate('/order/success', { state: { result } })
    } catch (err) {
      setSubmitError(err instanceof StorefrontApiError ? err.message : t('checkout.error.generic'))
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-12">
      <h1 className="font-display text-3xl font-semibold text-roast-900">{t('checkout.title')}</h1>

      <div className="mt-8 grid gap-10 lg:grid-cols-5 lg:items-start lg:gap-14">
        <motion.form
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          onSubmit={handleSubmit}
          noValidate
          className="lg:col-span-3"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{t('checkout.section.delivery')}</p>

          <div className="mt-4 space-y-4">
            <Field
              label={t('checkout.field.name')}
              value={form.customerName}
              onChange={updateField('customerName')}
              onBlur={markTouched('customerName')}
              error={touched.customerName ? fieldErrors.customerName : undefined}
            />
            <Field
              label={t('checkout.field.phone')}
              value={form.customerPhone}
              onChange={updateField('customerPhone')}
              onBlur={markTouched('customerPhone')}
              error={touched.customerPhone ? fieldErrors.customerPhone : undefined}
              type="tel"
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label={t('checkout.field.address')}
                value={form.deliveryAddress}
                onChange={updateField('deliveryAddress')}
                onBlur={markTouched('deliveryAddress')}
                error={touched.deliveryAddress ? fieldErrors.deliveryAddress : undefined}
              />
              <Field
                label={t('checkout.field.area')}
                value={form.deliveryArea}
                onChange={updateField('deliveryArea')}
                onBlur={markTouched('deliveryArea')}
                error={touched.deliveryArea ? fieldErrors.deliveryArea : undefined}
              />
            </div>
            <Field label={t('checkout.field.notes')} value={form.notes} onChange={updateField('notes')} multiline />
          </div>

          <div className="mt-6 flex items-start gap-3 rounded-2xl bg-cream-deep p-4">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white text-wehbi-red-600">
              <BanknoteIcon />
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{t('checkout.payment.label')}</p>
              <p className="font-semibold text-roast-900">{t('checkout.payment.cod')}</p>
              <p className="mt-0.5 text-sm text-stone-500">{t('checkout.payment.codDescription')}</p>
            </div>
          </div>

          {submitError && (
            <p role="alert" className="mt-4 text-sm text-wehbi-red-700">
              {submitError}
            </p>
          )}

          <StorefrontButton type="submit" disabled={submitting} className="mt-6 w-full">
            {submitting ? t('checkout.submitting') : t('checkout.placeOrder')}
          </StorefrontButton>
        </motion.form>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: 'easeOut', delay: 0.1 }}
          className="lg:col-span-2"
        >
          <div className="rounded-3xl bg-white p-6 shadow-[0_20px_45px_-24px_rgba(44,28,17,0.25)] ring-1 ring-stone-100 lg:sticky lg:top-24">
            <h2 className="font-display text-lg font-semibold text-roast-900">{t('order.summary.title')}</h2>
            <ul className="mt-4 divide-y divide-stone-200">
              {items.map((item) => {
                const name = localizedField(item.nameEn, item.nameAr, language)
                const price = Number(item.unitPriceSnapshot)
                const quantity = item.sellingMode === 'weight' ? (item.weightGrams ?? 0) / 1000 : (item.quantity ?? 0)
                return (
                  <li key={item.productId} className="flex justify-between gap-3 py-3 text-sm first:pt-0">
                    <span className="text-roast-900">{name}</span>
                    <span className="shrink-0 font-medium text-roast-900">{formatMoneyFixed(price * quantity)}</span>
                  </li>
                )
              })}
            </ul>
            <div className="mt-2 flex justify-between border-t border-stone-200 pt-4">
              <span className="font-semibold text-roast-900">{t('cart.orderTotal')}</span>
              <span className="text-xl font-semibold text-wehbi-red-700">{formatMoneyFixed(subtotal)}</span>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

interface FieldProps {
  label: string
  value: string
  onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void
  onBlur?: () => void
  error?: string
  type?: string
  multiline?: boolean
}

function Field({ label, value, onChange, onBlur, error, type = 'text', multiline = false }: FieldProps) {
  const sharedClass = `w-full border bg-white px-4 py-2.5 text-sm text-roast-900 shadow-[0_1px_3px_rgba(44,28,17,0.06)] transition-all duration-200 placeholder:text-stone-400 focus:outline-none focus:ring-4 ${
    error
      ? 'border-wehbi-red-300 focus:border-wehbi-red-500 focus:ring-wehbi-red-100'
      : 'border-stone-300 focus:border-wehbi-red-400 focus:ring-wehbi-red-100'
  }`

  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</span>
      {multiline ? (
        <textarea value={value} onChange={onChange} onBlur={onBlur} rows={3} className={`${sharedClass} resize-none rounded-2xl`} />
      ) : (
        <input type={type} value={value} onChange={onChange} onBlur={onBlur} className={`${sharedClass} rounded-full`} />
      )}
      {error && (
        <span role="alert" className="mt-1.5 block text-xs text-wehbi-red-700">
          {error}
        </span>
      )}
    </label>
  )
}
