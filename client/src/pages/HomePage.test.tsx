import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as storefrontApi from '../api/storefront'
import { LanguageProvider } from '../i18n/LanguageContext'
import type { StorefrontCategory, StorefrontProduct } from '../types/storefront'
import { HomePage } from './HomePage'

const STORAGE_KEY = 'wehbi-nuts-storefront-language'

vi.mock('../api/storefront', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/storefront')>()
  return {
    ...actual,
    listStorefrontCategories: vi.fn(),
    listStorefrontProducts: vi.fn(),
  }
})

const OFFICIAL_CATEGORIES: StorefrontCategory[] = [
  { id: '1', name_en: 'Coffee', name_ar: 'قهوة', slug: 'coffee' },
  { id: '2', name_en: 'Dried Fruits', name_ar: 'فواكه مجففة', slug: 'dried-fruits' },
  { id: '3', name_en: 'Nuts', name_ar: 'مكسرات', slug: 'nuts' },
  { id: '4', name_en: 'Snacks & Sweets', name_ar: 'وجبات خفيفة وحلويات', slug: 'snacks-sweets' },
  { id: '5', name_en: 'Seeds', name_ar: 'بذور', slug: 'seeds' },
  { id: '6', name_en: 'Spice & Herbs', name_ar: 'بهارات وأعشاب', slug: 'spice-herbs' },
  { id: '7', name_en: 'Gifts', name_ar: 'هدايا', slug: 'gifts' },
]

function makeProduct(overrides: Partial<StorefrontProduct> = {}): StorefrontProduct {
  return {
    id: 'p1',
    name_en: 'Roasted Almonds',
    name_ar: 'لوز محمص',
    description_en: null,
    description_ar: null,
    brand: null,
    category: OFFICIAL_CATEGORIES[2],
    selling_mode: 'weight',
    package_weight: null,
    price: '20.00',
    stock_status: 'in_stock',
    image: null,
    ...overrides,
  }
}

function renderHome() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  )
}

describe('HomePage', () => {
  beforeEach(() => {
    vi.mocked(storefrontApi.listStorefrontCategories).mockResolvedValue(OFFICIAL_CATEGORIES)
    vi.mocked(storefrontApi.listStorefrontProducts).mockResolvedValue([])
  })

  it('shows a hero with concise copy and a Shop call to action', () => {
    renderHome()

    expect(screen.getByText(/Freshly roasted/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Shop Now' })).toHaveAttribute('href', '/shop')
  })

  it('shows all seven official categories under Shop by Category', async () => {
    renderHome()

    expect(await screen.findByRole('heading', { name: 'Shop by Category' })).toBeInTheDocument()
    for (const category of OFFICIAL_CATEGORIES) {
      expect(await screen.findByText(category.name_en)).toBeInTheDocument()
    }
  })

  it('links each category tile to its category page', async () => {
    renderHome()

    const nutsLink = await screen.findByRole('link', { name: /Nuts/ })
    expect(nutsLink).toHaveAttribute('href', '/category/nuts')
  })

  it('shows real featured products from the catalog, not fake/hard-coded ones', async () => {
    vi.mocked(storefrontApi.listStorefrontProducts).mockImplementation(async (params) => {
      if (params?.limit) {
        return [makeProduct({ id: 'p1', name_en: 'Roasted Almonds' }), makeProduct({ id: 'p2', name_en: 'Turkish Coffee' })]
      }
      return []
    })

    renderHome()

    expect(await screen.findByText('Roasted Almonds')).toBeInTheDocument()
    expect(await screen.findByText('Turkish Coffee')).toBeInTheDocument()
    expect(storefrontApi.listStorefrontProducts).toHaveBeenCalledWith(expect.objectContaining({ limit: 4 }))
  })

  it('shows one additional creative/personality section', () => {
    renderHome()

    expect(screen.getByText(/Treat yourself/)).toBeInTheDocument()
  })

  describe('in Arabic', () => {
    beforeEach(() => {
      window.localStorage.setItem(STORAGE_KEY, 'ar')
    })

    afterEach(() => {
      window.localStorage.removeItem(STORAGE_KEY)
    })

    it('shows Arabic category names instead of English ones', async () => {
      render(
        <LanguageProvider>
          <MemoryRouter>
            <HomePage />
          </MemoryRouter>
        </LanguageProvider>,
      )

      expect(await screen.findByText('قهوة')).toBeInTheDocument()
      expect(await screen.findByText('هدايا')).toBeInTheDocument()
      expect(screen.queryByText('Coffee')).not.toBeInTheDocument()
    })

    it('translates the fixed hero and section headings', async () => {
      render(
        <LanguageProvider>
          <MemoryRouter>
            <HomePage />
          </MemoryRouter>
        </LanguageProvider>,
      )

      expect(await screen.findByRole('heading', { name: 'تسوّق حسب الفئة' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'تسوّق الآن' })).toBeInTheDocument()
    })
  })
})
