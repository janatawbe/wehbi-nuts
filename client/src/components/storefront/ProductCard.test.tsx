import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { LanguageProvider } from '../../i18n/LanguageContext'
import type { StorefrontProduct } from '../../types/storefront'
import { ProductCard } from './ProductCard'

function makeProduct(overrides: Partial<StorefrontProduct> = {}): StorefrontProduct {
  return {
    id: 'e3b0c442-98fc-1c14-9afb-abc123456789',
    name_en: 'Roasted Almonds',
    name_ar: 'لوز محمص',
    description_en: null,
    description_ar: null,
    brand: null,
    category: { id: 'c1', name_en: 'Nuts', name_ar: 'مكسرات', slug: 'nuts' },
    selling_mode: 'weight',
    package_weight: null,
    price: '20.00',
    stock_status: 'in_stock',
    image: null,
    ...overrides,
  }
}

function renderCard(product: StorefrontProduct) {
  return render(
    <MemoryRouter>
      <ProductCard product={product} />
    </MemoryRouter>,
  )
}

const STORAGE_KEY = 'wehbi-nuts-storefront-language'

function renderCardInArabic(product: StorefrontProduct) {
  window.localStorage.setItem(STORAGE_KEY, 'ar')
  return render(
    <LanguageProvider>
      <MemoryRouter>
        <ProductCard product={product} />
      </MemoryRouter>
    </LanguageProvider>,
  )
}

describe('ProductCard', () => {
  it('shows a whole-number weight price as "$X / kg"', () => {
    renderCard(makeProduct({ selling_mode: 'weight', price: '20.00' }))
    expect(screen.getByText('$20 / kg')).toBeInTheDocument()
  })

  it('shows a fractional weight price with cents', () => {
    renderCard(makeProduct({ selling_mode: 'weight', price: '7.50' }))
    expect(screen.getByText('$7.50 / kg')).toBeInTheDocument()
  })

  it('shows a unit price with two decimals and its package weight in grams', () => {
    renderCard(makeProduct({ selling_mode: 'unit', price: '5', package_weight: '0.500' }))
    expect(screen.getByText('$5.00')).toBeInTheDocument()
    expect(screen.getByText(/500 g package/)).toBeInTheDocument()
  })

  it('shows a unit price with no secondary line when there is no package weight', () => {
    renderCard(makeProduct({ selling_mode: 'unit', price: '12.00', package_weight: null }))
    expect(screen.getByText('$12.00')).toBeInTheDocument()
    expect(screen.queryByText(/package/)).not.toBeInTheDocument()
  })

  it('shows the product name and is a link to its detail page', () => {
    const product = makeProduct({ id: 'abc-123', name_en: 'Turkish Coffee' })
    renderCard(product)

    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', '/product/abc-123')
    expect(screen.getByText('Turkish Coffee')).toBeInTheDocument()
  })

  it('shows a sold-out marker for an out-of-stock product', () => {
    renderCard(makeProduct({ stock_status: 'out_of_stock' }))
    expect(screen.getByText('Sold out')).toBeInTheDocument()
  })

  it('never shows internal/admin fields such as SKU, IDs, or category IDs', () => {
    const product = makeProduct({ id: 'e3b0c442-98fc-1c14-9afb-abc123456789' })
    renderCard(product)

    expect(screen.queryByText(product.id)).not.toBeInTheDocument()
    expect(screen.queryByText(/sku/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/review/i)).not.toBeInTheDocument()
  })

  it('shows the Arabic name when Arabic is the active language', () => {
    const product = makeProduct({ name_en: 'Turkish Coffee', name_ar: 'قهوة تركية' })
    renderCardInArabic(product)

    expect(screen.getByText('قهوة تركية')).toBeInTheDocument()
    expect(screen.queryByText('Turkish Coffee')).not.toBeInTheDocument()
    window.localStorage.removeItem('wehbi-nuts-storefront-language')
  })

  it('falls back to the English name in Arabic mode when the Arabic name is empty', () => {
    const product = makeProduct({ name_en: 'Turkish Coffee', name_ar: '' })
    renderCardInArabic(product)

    expect(screen.getByText('Turkish Coffee')).toBeInTheDocument()
    window.localStorage.removeItem('wehbi-nuts-storefront-language')
  })

  it('shows the Arabic unit abbreviation for a weight-mode price in Arabic', () => {
    const product = makeProduct({ selling_mode: 'weight', price: '20.00' })
    renderCardInArabic(product)

    expect(screen.getByText('$20 / كغ')).toBeInTheDocument()
    window.localStorage.removeItem('wehbi-nuts-storefront-language')
  })
})
