import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { LanguageProvider } from '../../i18n/LanguageContext'
import type { StorefrontCategory } from '../../types/storefront'
import { CategoryTile } from './CategoryTile'

const STORAGE_KEY = 'wehbi-nuts-storefront-language'

function makeCategory(overrides: Partial<StorefrontCategory> = {}): StorefrontCategory {
  return { id: '1', name_en: 'Nuts', name_ar: 'مكسرات', slug: 'nuts', ...overrides }
}

function renderTile(category: StorefrontCategory) {
  return render(
    <MemoryRouter>
      <CategoryTile category={category} />
    </MemoryRouter>,
  )
}

function renderTileInArabic(category: StorefrontCategory) {
  window.localStorage.setItem(STORAGE_KEY, 'ar')
  return render(
    <LanguageProvider>
      <MemoryRouter>
        <CategoryTile category={category} />
      </MemoryRouter>
    </LanguageProvider>,
  )
}

describe('CategoryTile', () => {
  it('shows the English name by default and links to the category page', () => {
    renderTile(makeCategory())

    expect(screen.getByText('Nuts')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Nuts/ })).toHaveAttribute('href', '/category/nuts')
  })

  it('shows the Arabic name when Arabic is active', () => {
    renderTileInArabic(makeCategory({ name_en: 'Nuts', name_ar: 'مكسرات' }))

    expect(screen.getByText('مكسرات')).toBeInTheDocument()
    expect(screen.queryByText('Nuts')).not.toBeInTheDocument()
    window.localStorage.removeItem(STORAGE_KEY)
  })

  it('falls back to the English name in Arabic mode when the Arabic name is empty', () => {
    renderTileInArabic(makeCategory({ name_en: 'Gifts', name_ar: '' }))

    expect(screen.getByText('Gifts')).toBeInTheDocument()
    window.localStorage.removeItem(STORAGE_KEY)
  })
})
