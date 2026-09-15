import { motion } from 'framer-motion'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import wehbiLogoMark from '../../assets/wehbi-logo-mark.png'
import { useCart } from '../../cart/CartContext'
import { useLanguage } from '../../i18n/LanguageContext'
import { LanguageSwitcher } from './LanguageSwitcher'

const NAV_LINK_CLASS = ({ isActive }: { isActive: boolean }) =>
  `rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
    isActive ? 'text-wehbi-red-700' : 'text-roast-800 hover:text-wehbi-red-700'
  }`

function CartIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M3 4h2l2.4 12.2a2 2 0 0 0 2 1.6h7.2a2 2 0 0 0 2-1.6L20.5 8H6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="9.5" cy="20.5" r="1.3" fill="currentColor" stroke="none" />
      <circle cx="17" cy="20.5" r="1.3" fill="currentColor" stroke="none" />
    </svg>
  )
}

function SearchIcon({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" />
      <path d="m20 20-3.4-3.4" strokeLinecap="round" />
    </svg>
  )
}

export function StorefrontHeader() {
  const navigate = useNavigate()
  const { t } = useLanguage()
  const { itemCount } = useCart()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  // A brief "look, something landed in the cart" pulse around the cart
  // icon -- fires only when itemCount actually GROWS (never on initial
  // mount/page load with an already-persisted cart, and never on
  // removal). previousCount starts equal to itemCount so a fresh mount
  // never spuriously pulses.
  const previousCountRef = useRef(itemCount)
  const [pulseKey, setPulseKey] = useState(0)
  useEffect(() => {
    if (itemCount > previousCountRef.current) {
      setPulseKey((key) => key + 1)
    }
    previousCountRef.current = itemCount
  }, [itemCount])

  const handleSearchSubmit = (event: FormEvent) => {
    event.preventDefault()
    setMobileOpen(false)
    navigate(searchTerm.trim() ? `/shop?search=${encodeURIComponent(searchTerm.trim())}` : '/shop')
  }

  return (
    <header className="sticky top-0 z-30 border-b border-roast-900/15 bg-cream-deep/95 shadow-[0_10px_24px_-8px_rgba(44,28,17,0.32)] backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 sm:px-6">
        <Link to="/" className="flex items-center gap-2.5 shrink-0" aria-label="Wehbi Nuts home">
          <img src={wehbiLogoMark} alt="Wehbi Nuts" className="h-10 w-10 sm:h-11 sm:w-11" />
          <span className="font-display text-lg font-semibold tracking-tight text-roast-900 sm:text-xl">
            Wehbi Nuts
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          <NavLink to="/" end className={NAV_LINK_CLASS}>
            {t('nav.home')}
          </NavLink>
          <NavLink to="/shop" className={NAV_LINK_CLASS}>
            {t('nav.shop')}
          </NavLink>
        </nav>

        <form onSubmit={handleSearchSubmit} className="ms-auto hidden max-w-sm flex-1 items-center md:flex">
          <label htmlFor="storefront-search" className="sr-only">
            {t('nav.search.label')}
          </label>
          <div className="group flex w-full items-center gap-2.5 rounded-full border border-stone-200 bg-white px-4 py-2.5 shadow-[0_1px_3px_rgba(44,28,17,0.06)] ring-1 ring-transparent transition-all duration-200 focus-within:border-wehbi-red-300 focus-within:shadow-[0_6px_20px_-6px_rgba(195,28,37,0.25)] focus-within:ring-wehbi-red-100">
            <SearchIcon className="h-4 w-4 shrink-0 text-stone-500 transition-colors duration-200 group-focus-within:text-wehbi-red-600" />
            <input
              id="storefront-search"
              type="search"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={t('nav.search.placeholder')}
              className="w-full bg-transparent text-sm text-roast-900 placeholder:text-stone-400 focus:outline-none"
            />
          </div>
        </form>

        <LanguageSwitcher className="hidden md:inline-flex" />

        <Link
          to="/cart"
          aria-label={t('nav.cart')}
          className="relative ms-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-roast-800 transition-colors hover:bg-roast-900/5 md:ms-0"
        >
          {pulseKey > 0 && (
            <motion.span
              key={pulseKey}
              initial={{ scale: 0.7, opacity: 0.55 }}
              animate={{ scale: 1.7, opacity: 0 }}
              transition={{ duration: 0.6, ease: 'easeOut' }}
              className="absolute inset-0 rounded-full bg-wehbi-red-400"
              aria-hidden="true"
            />
          )}
          <CartIcon />
          <motion.span
            key={itemCount}
            initial={{ scale: 0.6 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 500, damping: 20 }}
            className="absolute -end-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-wehbi-red-600 text-[10px] font-semibold text-white"
          >
            {itemCount}
          </motion.span>
        </Link>

        <button
          type="button"
          onClick={() => setMobileOpen((prev) => !prev)}
          aria-expanded={mobileOpen}
          aria-label={t('nav.menu')}
          className="flex h-10 w-10 items-center justify-center rounded-full text-roast-800 hover:bg-roast-900/5 md:hidden"
        >
          <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            {mobileOpen ? (
              <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
            ) : (
              <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
            )}
          </svg>
        </button>
      </div>

      {mobileOpen && (
        <div className="border-t border-stone-200 bg-cream-deep px-4 pb-5 pt-3 md:hidden">
          <div className="mb-3 flex justify-end">
            <LanguageSwitcher />
          </div>
          <form onSubmit={handleSearchSubmit} className="mb-3 flex items-center gap-2.5 rounded-full border border-stone-200 bg-white px-4 py-2.5 shadow-[0_1px_3px_rgba(44,28,17,0.06)] ring-1 ring-transparent focus-within:border-wehbi-red-300 focus-within:ring-wehbi-red-100">
            <SearchIcon className="h-4 w-4 shrink-0 text-stone-500" />
            <label htmlFor="storefront-search-mobile" className="sr-only">
              {t('nav.search.label')}
            </label>
            <input
              id="storefront-search-mobile"
              type="search"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={t('nav.search.placeholder')}
              className="w-full bg-transparent text-sm text-roast-900 placeholder:text-stone-400/80 focus:outline-none"
            />
          </form>
          <nav className="flex flex-col gap-1" aria-label="Main">
            <NavLink to="/" end onClick={() => setMobileOpen(false)} className="rounded-lg px-3 py-2 text-sm font-medium text-roast-800">
              {t('nav.home')}
            </NavLink>
            <NavLink to="/shop" onClick={() => setMobileOpen(false)} className="rounded-lg px-3 py-2 text-sm font-medium text-roast-800">
              {t('nav.shop')}
            </NavLink>
          </nav>
        </div>
      )}
    </header>
  )
}
