import { Outlet } from 'react-router-dom'
import { useLanguage } from '../../i18n/LanguageContext'
import { StorefrontFooter } from './StorefrontFooter'
import { StorefrontHeader } from './StorefrontHeader'

/** The customer storefront's root -- the ONLY place (along with
 * NotFoundPage, the sole customer-facing page rendered outside this
 * layout) that ever sets `dir`/`lang` for Arabic. Both are set on this
 * wrapper `<div>`, never on `<html>`/`document`, so they can never leak
 * into the separately-rooted AdminLayout branch of the route tree --
 * RTL and the Arabic font stay scoped to exactly this subtree by
 * construction, not by a runtime check. */
export function StorefrontLayout() {
  const { language, direction } = useLanguage()

  return (
    <div
      lang={language}
      dir={direction}
      data-storefront-lang={language}
      className="flex min-h-dvh flex-col bg-cream font-body"
    >
      <StorefrontHeader />
      <main className="flex-1">
        <Outlet />
      </main>
      <StorefrontFooter />
    </div>
  )
}
