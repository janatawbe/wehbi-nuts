import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AdminLayout } from '../admin/AdminLayout'
import { LanguageProvider } from '../../i18n/LanguageContext'
import { StorefrontLayout } from './StorefrontLayout'

const STORAGE_KEY = 'wehbi-nuts-storefront-language'

function renderStorefront() {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<StorefrontLayout />}>
            <Route path="/" element={<p>Home content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

describe('StorefrontLayout', () => {
  it('defaults to English/LTR on its own root element', () => {
    renderStorefront()

    const root = screen.getByText('Home content').closest('[data-storefront-lang]')
    expect(root).toHaveAttribute('lang', 'en')
    expect(root).toHaveAttribute('dir', 'ltr')
  })

  it('switches to Arabic/RTL on its own root element when Arabic is persisted', () => {
    window.localStorage.setItem(STORAGE_KEY, 'ar')

    renderStorefront()

    const root = screen.getByText('Home content').closest('[data-storefront-lang]')
    expect(root).toHaveAttribute('lang', 'ar')
    expect(root).toHaveAttribute('dir', 'rtl')

    window.localStorage.removeItem(STORAGE_KEY)
  })

  it('never sets dir/lang on the document root itself', () => {
    window.localStorage.setItem(STORAGE_KEY, 'ar')

    renderStorefront()

    expect(document.documentElement).not.toHaveAttribute('dir')

    window.localStorage.removeItem(STORAGE_KEY)
  })
})

describe('Admin stays English/LTR regardless of the storefront language', () => {
  it('AdminLayout renders plain English text with no dir/lang override, even with Arabic persisted', () => {
    window.localStorage.setItem(STORAGE_KEY, 'ar')

    render(
      <LanguageProvider>
        <MemoryRouter initialEntries={['/admin']}>
          <Routes>
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<p>Admin content</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </LanguageProvider>,
    )

    expect(screen.getByText('Wehbi Nuts Admin')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Digitizer' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Review' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Catalog' })).toBeInTheDocument()

    const adminRoot = screen.getByText('Wehbi Nuts Admin').closest('div')
    expect(adminRoot).not.toHaveAttribute('dir', 'rtl')
    expect(document.documentElement).not.toHaveAttribute('dir')

    window.localStorage.removeItem(STORAGE_KEY)
  })
})
