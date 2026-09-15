import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as storefrontApi from '../api/storefront'
import { StorefrontApiError } from '../api/storefront'
import type { StorefrontCategory, StorefrontProduct } from '../types/storefront'
import { ShopPage } from './ShopPage'

vi.mock('../api/storefront', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/storefront')>()
  return {
    ...actual,
    listStorefrontCategories: vi.fn(),
    listStorefrontProducts: vi.fn(),
  }
})

const CATEGORIES: StorefrontCategory[] = [
  { id: '1', name_en: 'Nuts', name_ar: 'مكسرات', slug: 'nuts' },
  { id: '2', name_en: 'Coffee', name_ar: 'قهوة', slug: 'coffee' },
]

function makeProduct(overrides: Partial<StorefrontProduct> = {}): StorefrontProduct {
  return {
    id: 'p1',
    name_en: 'Roasted Almonds',
    name_ar: 'لوز محمص',
    description_en: null,
    description_ar: null,
    brand: null,
    category: CATEGORIES[0],
    selling_mode: 'weight',
    package_weight: null,
    price: '20.00',
    stock_status: 'in_stock',
    image: null,
    ...overrides,
  }
}

function renderShop(initialPath = '/shop') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ShopPage />
    </MemoryRouter>,
  )
}

describe('ShopPage', () => {
  beforeEach(() => {
    vi.mocked(storefrontApi.listStorefrontCategories).mockResolvedValue(CATEGORIES)
    vi.mocked(storefrontApi.listStorefrontProducts).mockResolvedValue([makeProduct()])
  })

  it('shows a loading state while products are being fetched', () => {
    vi.mocked(storefrontApi.listStorefrontProducts).mockReturnValue(new Promise(() => {}))
    renderShop()

    expect(screen.getByTestId('product-grid-loading')).toBeInTheDocument()
  })

  it('shows the product grid once loaded', async () => {
    renderShop()

    expect(await screen.findByText('Roasted Almonds')).toBeInTheDocument()
  })

  it('shows a sensible empty state when nothing matches', async () => {
    vi.mocked(storefrontApi.listStorefrontProducts).mockResolvedValue([])
    renderShop()

    expect(await screen.findByTestId('product-grid-empty')).toBeInTheDocument()
  })

  it('shows an error state when the request fails', async () => {
    vi.mocked(storefrontApi.listStorefrontProducts).mockRejectedValue(new StorefrontApiError('Server error.', 500))
    renderShop()

    expect(await screen.findByTestId('product-grid-error')).toHaveTextContent('Server error.')
  })

  it('shows category filter chips including All', async () => {
    renderShop()

    expect(await screen.findByRole('tab', { name: 'All' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Nuts' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Coffee' })).toBeInTheDocument()
  })

  it('clicking a category chip filters the product request by that category', async () => {
    renderShop()
    fireEvent.click(await screen.findByRole('tab', { name: 'Coffee' }))

    await waitFor(() =>
      expect(storefrontApi.listStorefrontProducts).toHaveBeenLastCalledWith(
        expect.objectContaining({ category: 'coffee' }),
      ),
    )
  })

  it('reads the initial category from the URL', async () => {
    renderShop('/shop?category=nuts')

    await waitFor(() =>
      expect(storefrontApi.listStorefrontProducts).toHaveBeenCalledWith(expect.objectContaining({ category: 'nuts' })),
    )
    expect(await screen.findByRole('tab', { name: 'Nuts', selected: true })).toBeInTheDocument()
  })

  it('reads the initial search term from the URL (set by the header search box)', async () => {
    renderShop('/shop?search=almond')

    await waitFor(() =>
      expect(storefrontApi.listStorefrontProducts).toHaveBeenCalledWith(expect.objectContaining({ search: 'almond' })),
    )
  })

  it('has no Shop-page search input -- search happens only through the header', async () => {
    renderShop()
    await screen.findByRole('tab', { name: 'All' })

    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
    expect(screen.queryByPlaceholderText('Search products...')).not.toBeInTheDocument()
  })
})
