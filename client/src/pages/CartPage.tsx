import { Link } from 'react-router-dom'
import { StorefrontLinkButton } from '../components/storefront/StorefrontButton'
import { useLanguage } from '../i18n/LanguageContext'

/** A real page (not a dead icon) so the header's cart entry point goes
 * somewhere honest -- cart state/checkout is Milestone 10 work; this page
 * makes that clear rather than pretending a cart already works. */
export function CartPage() {
  const { t } = useLanguage()

  return (
    <div className="mx-auto max-w-2xl px-4 py-20 text-center sm:px-6">
      <h1 className="font-display text-2xl font-semibold text-roast-900">{t('cart.empty.title')}</h1>
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
