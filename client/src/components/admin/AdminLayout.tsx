import { NavLink, Outlet } from 'react-router-dom'

const LINK_CLASS = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-2.5 py-1 text-sm font-medium ${
    isActive ? 'text-roast-800' : 'text-stone-500 hover:text-stone-800'
  }`

/** The internal admin area (Digitizer/Review/Catalog) -- a separate,
 * plainer layout from the customer storefront (see StorefrontLayout):
 * these are staff tools, not the brand experience, and must never share
 * navigation or visual identity with the customer-facing site (see
 * components/ui/Button and friends, kept exactly as they were). */
export function AdminLayout() {
  return (
    <div className="min-h-dvh bg-cream">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <p className="font-semibold tracking-tight text-roast-800">Wehbi Nuts Admin</p>
          <nav className="flex gap-1" aria-label="Admin">
            <NavLink to="/admin/digitizer" className={LINK_CLASS}>
              Digitizer
            </NavLink>
            <NavLink to="/admin/review" className={LINK_CLASS}>
              Review
            </NavLink>
            <NavLink to="/admin/catalog" className={LINK_CLASS}>
              Catalog
            </NavLink>
          </nav>
        </div>
      </header>
      <Outlet />
    </div>
  )
}
