import { Link } from 'react-router-dom'
import { StorefrontLinkButton } from '../components/storefront/StorefrontButton'
import { forwardArrow } from '../i18n/translations'
import { useLanguage } from '../i18n/LanguageContext'

/** The one customer-facing page rendered OUTSIDE StorefrontLayout (it's
 * the app-wide catch-all route), so it applies `dir`/`lang` on its own
 * root the same way StorefrontLayout does -- see that component's
 * docstring for why this never leaks into the admin route tree. */
export function NotFoundPage() {
  const { language, direction, t } = useLanguage()

  return (
    <div
      lang={language}
      dir={direction}
      data-storefront-lang={language}
      className="mx-auto max-w-2xl px-4 py-24 text-center font-body sm:px-6"
    >
      <p className="font-display text-5xl font-semibold text-wehbi-red-600">404</p>
      <h1 className="mt-3 text-xl font-semibold text-roast-900">{t('notFound.title')}</h1>
      <p className="mt-2 text-sm text-stone-500">{t('notFound.body')}</p>
      <div className="mt-8">
        <StorefrontLinkButton to="/">{t('nav.backHome')}</StorefrontLinkButton>
      </div>
      <p className="mt-6 text-sm">
        <Link to="/shop" className="text-wehbi-red-700 hover:underline">
          {t('notFound.browseShop')} {forwardArrow(direction)}
        </Link>
      </p>
    </div>
  )
}
