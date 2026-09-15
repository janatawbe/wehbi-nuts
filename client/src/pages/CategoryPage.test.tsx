import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as storefrontApi from '../api/storefront'
import type { StorefrontCategory, StorefrontProduct } from '../types/storefront'
import { CategoryPage } from './CategoryPage'

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

function renderCategory(slug: string) {
  return render(
    <MemoryRouter initialEntries={[`/category/${slug}`]}>
      <Routes>
        <Route path="/category/:slug" element={<CategoryPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('CategoryPage', () => {
  beforeEach(() => {
    vi.mocked(storefrontApi.listStorefrontCategories).mockResolvedValue(CATEGORIES)
  })

  it('shows the category name as the heading and its products', async () => {
    vi.mocked(storefrontApi.listStorefrontProducts).mockResolvedValue([makeProduct()])
    renderCategory('nuts')

    expect(await screen.findByRole('heading', { name: 'Nuts' })).toBeInTheDocument()
    expect(await screen.findByText('Roasted Almonds')).toBeInTheDocument()
    expect(storefrontApi.listStorefrontProducts).toHaveBeenCalledWith(expect.objectContaining({ category: 'nuts' }))
  })

  it('shows a not-found state for an unknown category slug, without crashing', async () => {
    vi.mocked(storefrontApi.listStorefrontProducts).mockResolvedValue([])
    renderCategory('not-a-real-category')

    expect(await screen.findByText('Category not found')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Browse the full shop/ })).toHaveAttribute('href', '/shop')
  })

  it('shows an empty state for a real category with no products yet', async () => {
    vi.mocked(storefrontApi.listStorefrontProducts).mockResolvedValue([])
    renderCategory('coffee')

    expect(await screen.findByTestId('product-grid-empty')).toHaveTextContent('No products in this category yet.')
  })
})
