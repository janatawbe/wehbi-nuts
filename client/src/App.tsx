import { MotionConfig } from 'framer-motion'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AdminLayout } from './components/admin/AdminLayout'
import { StorefrontLayout } from './components/storefront/StorefrontLayout'
import { LanguageProvider } from './i18n/LanguageContext'
import { CartPage } from './pages/CartPage'
import { CatalogPage } from './pages/CatalogPage'
import { CategoryPage } from './pages/CategoryPage'
import { DigitizerPage } from './pages/DigitizerPage'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProductDetailPage } from './pages/ProductDetailPage'
import { ReviewPage } from './pages/ReviewPage'
import { ShopPage } from './pages/ShopPage'

// Milestone 9: Wehbi Nuts is the customer-facing store -- "/", "/shop",
// "/category/:slug", "/product/:id" -- while the Digitizer/Review/Catalog
// staff tools live entirely under "/admin/*", in their own layout, with
// their own (unchanged) pages and tests. The two never share navigation
// or visual identity; see StorefrontLayout vs. AdminLayout.
//
// LanguageProvider wraps the whole tree for convenience, but it is inert
// for the admin branch: AdminLayout and its pages never call
// useLanguage()/t(), so they always render their original English text
// regardless of the storefront's selected language. Only
// StorefrontLayout and NotFoundPage (the one page rendered outside that
// layout, at the catch-all route) actually apply `dir`/`lang` -- see
// their own components for where that scoping happens.
function App() {
  return (
    <LanguageProvider>
      <MotionConfig reducedMotion="user">
        <BrowserRouter>
          <Routes>
            <Route element={<StorefrontLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/shop" element={<ShopPage />} />
              <Route path="/category/:slug" element={<CategoryPage />} />
              <Route path="/product/:id" element={<ProductDetailPage />} />
              <Route path="/cart" element={<CartPage />} />
            </Route>

            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="digitizer" replace />} />
              <Route path="digitizer" element={<DigitizerPage />} />
              <Route path="review" element={<ReviewPage />} />
              <Route path="catalog" element={<CatalogPage />} />
            </Route>

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </BrowserRouter>
      </MotionConfig>
    </LanguageProvider>
  )
}

export default App
