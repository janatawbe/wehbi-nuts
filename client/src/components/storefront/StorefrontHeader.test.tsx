import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { LanguageProvider } from '../../i18n/LanguageContext'
import { StorefrontHeader } from './StorefrontHeader'

const STORAGE_KEY = 'wehbi-nuts-storefront-language'

function renderHeader(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="*" element={<StorefrontHeader />} />
      </Routes>
    </MemoryRouter>,
  )
}

function renderHeaderWithLanguageProvider(initialPath = '/') {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="*" element={<StorefrontHeader />} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

describe('StorefrontHeader', () => {
  it('renders the official logo image and the store name', () => {
    renderHeader()

    const logo = screen.getByAltText('Wehbi Nuts')
    expect(logo.tagName).toBe('IMG')
    expect(logo.getAttribute('src')).toMatch(/wehbi-logo-mark/)
    expect(screen.getAllByText('Wehbi Nuts').length).toBeGreaterThan(0)
  })

  it('shows Home and Shop, never Categories or an admin tool name', () => {
    renderHeader()

    expect(screen.getByRole('link', { name: 'Home' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Shop' })).toBeInTheDocument()
    expect(screen.queryByText('Categories')).not.toBeInTheDocument()
    expect(screen.queryByText('Digitizer')).not.toBeInTheDocument()
    expect(screen.queryByText('Review')).not.toBeInTheDocument()
    expect(screen.queryByText('Catalog')).not.toBeInTheDocument()
  })

  it('shows a cart entry point with a count badge', () => {
    renderHeader()

    const cartLink = screen.getByRole('link', { name: 'Cart' })
    expect(cartLink).toHaveAttribute('href', '/cart')
    expect(cartLink).toHaveTextContent('0')
  })

  it('submitting search navigates to /shop with the search term', async () => {
    function Probe() {
      return (
        <Routes>
          <Route path="/*" element={<StorefrontHeader />} />
          <Route path="/shop" element={<p>On shop page</p>} />
        </Routes>
      )
    }
    render(
      <MemoryRouter initialEntries={['/']}>
        <Probe />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByPlaceholderText('Search nuts, coffee, sweets...'), {
      target: { value: 'almonds' },
    })
    fireEvent.submit(screen.getByPlaceholderText('Search nuts, coffee, sweets...').closest('form')!)

    expect(await screen.findByText('On shop page')).toBeInTheDocument()
  })

  it('toggles the mobile menu open and closed', () => {
    renderHeader()
    const menuButton = screen.getByRole('button', { name: 'Menu' })

    expect(menuButton).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(menuButton)
    expect(menuButton).toHaveAttribute('aria-expanded', 'true')
  })

  describe('language switcher', () => {
    beforeEach(() => {
      window.localStorage.removeItem(STORAGE_KEY)
    })

    it('shows an EN | AR switcher with English active by default', () => {
      renderHeaderWithLanguageProvider()

      const en = screen.getByRole('button', { name: 'EN' })
      const ar = screen.getByRole('button', { name: 'AR' })
      expect(en).toHaveAttribute('aria-pressed', 'true')
      expect(ar).toHaveAttribute('aria-pressed', 'false')
    })

    it('switching to AR translates the header text (English to Arabic)', () => {
      renderHeaderWithLanguageProvider()

      fireEvent.click(screen.getByRole('button', { name: 'AR' }))

      expect(screen.getByRole('link', { name: 'الرئيسية' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'المتجر' })).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'Home' })).not.toBeInTheDocument()
    })

    it('switching back from AR to EN restores the English header text', () => {
      renderHeaderWithLanguageProvider()

      fireEvent.click(screen.getByRole('button', { name: 'AR' }))
      fireEvent.click(screen.getByRole('button', { name: 'EN' }))

      expect(screen.getByRole('link', { name: 'Home' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Shop' })).toBeInTheDocument()
    })

    it('persists the language choice so a remounted header keeps it', () => {
      const { unmount } = renderHeaderWithLanguageProvider()
      fireEvent.click(screen.getByRole('button', { name: 'AR' }))
      unmount()

      renderHeaderWithLanguageProvider()

      expect(screen.getByRole('link', { name: 'الرئيسية' })).toBeInTheDocument()
    })
  })
})
