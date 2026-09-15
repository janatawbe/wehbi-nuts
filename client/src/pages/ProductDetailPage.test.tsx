import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as storefrontApi from '../api/storefront'
import { StorefrontApiError } from '../api/storefront'
import type { StorefrontProduct } from '../types/storefront'
import { ProductDetailPage } from './ProductDetailPage'

vi.mock('../api/storefront', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/storefront')>()
  return {
    ...actual,
    getStorefrontProduct: vi.fn(),
  }
})

function makeProduct(overrides: Partial<StorefrontProduct> = {}): StorefrontProduct {
  return {
    id: 'p1',
    name_en: 'Roasted Almonds',
    name_ar: 'لوز محمص',
    description_en: 'Freshly roasted daily.',
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

function renderDetail(id = 'p1') {
  return render(
    <MemoryRouter initialEntries={[`/product/${id}`]}>
      <Routes>
        <Route path="/product/:id" element={<ProductDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProductDetailPage', () => {
  it('shows a loading state before the product arrives', () => {
    vi.mocked(storefrontApi.getStorefrontProduct).mockReturnValue(new Promise(() => {}))
    renderDetail()

    expect(screen.getByTestId('product-detail-loading')).toBeInTheDocument()
  })

  it('shows name, description, and category for a loaded product', async () => {
    vi.mocked(storefrontApi.getStorefrontProduct).mockResolvedValue(makeProduct())
    renderDetail()

    expect(await screen.findByRole('heading', { name: 'Roasted Almonds' })).toBeInTheDocument()
    expect(screen.getByText('Freshly roasted daily.')).toBeInTheDocument()
    expect(screen.getAllByText('Nuts').length).toBeGreaterThan(0)
  })

  it('makes clear a weight product is priced per kilogram', async () => {
    vi.mocked(storefrontApi.getStorefrontProduct).mockResolvedValue(
      makeProduct({ selling_mode: 'weight', price: '20.00' }),
    )
    renderDetail()

    await screen.findByRole('heading', { name: 'Roasted Almonds' })
    expect(screen.getByText('$20 / kg')).toBeInTheDocument()
    expect(screen.getByText('priced per kilogram')).toBeInTheDocument()
  })

  it('shows package weight for a unit product', async () => {
    vi.mocked(storefrontApi.getStorefrontProduct).mockResolvedValue(
      makeProduct({ selling_mode: 'unit', price: '5.00', package_weight: '0.500' }),
    )
    renderDetail()

    await screen.findByRole('heading', { name: 'Roasted Almonds' })
    expect(screen.getByText('$5.00')).toBeInTheDocument()
    expect(screen.getByText('500 g package')).toBeInTheDocument()
  })

  it('shows a tasteful fallback, not a broken image, when there is no product image', async () => {
    vi.mocked(storefrontApi.getStorefrontProduct).mockResolvedValue(makeProduct({ image: null }))
    renderDetail()

    await screen.findByRole('heading', { name: 'Roasted Almonds' })
    // No real <img> element at all (never a broken-image icon) -- instead
    // a decorative, accessibly-labeled div stands in for the image.
    expect(document.querySelector('img')).toBeNull()
    expect(screen.getByRole('img', { name: 'Roasted Almonds' })).toBeInTheDocument()
  })

  it('shows an out-of-stock badge when appropriate', async () => {
    vi.mocked(storefrontApi.getStorefrontProduct).mockResolvedValue(makeProduct({ stock_status: 'out_of_stock' }))
    renderDetail()

    expect(await screen.findByText('Out of stock')).toBeInTheDocument()
  })

  it('never shows an Add to Cart control since cart functionality does not exist yet', async () => {
    vi.mocked(storefrontApi.getStorefrontProduct).mockResolvedValue(makeProduct())
    renderDetail()

    await screen.findByRole('heading', { name: 'Roasted Almonds' })
    expect(screen.queryByRole('button', { name: /add to cart/i })).not.toBeInTheDocument()
  })

  it('shows a not-found state for a missing product', async () => {
    vi.mocked(storefrontApi.getStorefrontProduct).mockRejectedValue(new StorefrontApiError('Product not found.', 404))
    renderDetail('unknown-id')

    expect(await screen.findByText('Product not found')).toBeInTheDocument()
  })
})
