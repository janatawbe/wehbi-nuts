import { MotionConfig } from 'framer-motion'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AdminLayout } from './components/admin/AdminLayout'
import { StorefrontLayout } from './components/storefront/StorefrontLayout'
import { CartProvider } from './cart/CartContext'
import { LanguageProvider } from './i18n/LanguageContext'
import { CartPage } from './pages/CartPage'
import { CatalogPage } from './pages/CatalogPage'
import { CategoryPage } from './pages/CategoryPage'
import { CheckoutPage } from './pages/CheckoutPage'
import { DigitizerPage } from './pages/DigitizerPage'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { OrderSuccessPage } from './pages/OrderSuccessPage'
import { ProductDetailPage } from './pages/ProductDetailPage'
import { ReviewPage } from './pages/ReviewPage'
import { ShopPage } from './pages/ShopPage'

// Milestone 9: Wehbi Nuts is the customer-facing store -- "/", "/shop",
// "/category/:slug", "/product/:id" -- while the Digitizer/Review/Catalog
// staff tools live entirely under "/admin/*", in their own layout, with
// their own (unchanged) pages and tests. The two never share navigation
// or visual identity; see StorefrontLayout vs. AdminLayout.
//
// LanguageProvider/CartProvider both wrap the whole tree for convenience,
// but are inert for the admin branch: AdminLayout and its pages never
// call useLanguage()/useCart(), so they always render their original
// English, cart-free UI regardless of the storefront's language or cart
// state. Only StorefrontLayout and NotFoundPage (the one page rendered
// outside that layout, at the catch-all route) actually apply `dir`/
// `lang` -- see their own components for where that scoping happens.
//
// Milestone 10: "/checkout" and "/order/success" stay inside
// StorefrontLayout (keeping the header/footer chrome, like every other
// customer page) -- OrderSuccessPage reads its confirmed order from
// navigation state only (see that page's own docstring), never from a
// public order-lookup endpoint, which this milestone deliberately does
// not implement.
function App() {
  return (
    <LanguageProvider>
      <CartProvider>
        <MotionConfig reducedMotion="user">
          <BrowserRouter>
            <Routes>
              <Route element={<StorefrontLayout />}>
                <Route path="/" element={<HomePage />} />
                <Route path="/shop" element={<ShopPage />} />
                <Route path="/category/:slug" element={<CategoryPage />} />
                <Route path="/product/:id" element={<ProductDetailPage />} />
                <Route path="/cart" element={<CartPage />} />
                <Route path="/checkout" element={<CheckoutPage />} />
                <Route path="/order/success" element={<OrderSuccessPage />} />
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
      </CartProvider>
    </LanguageProvider>
  )
}

export default App
