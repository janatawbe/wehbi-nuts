import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./api/digitizer', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api/digitizer')>()
  return {
    ...actual,
    listDigitizerJobs: vi.fn().mockResolvedValue([]),
    uploadDigitizerJob: vi.fn(),
  }
})

vi.mock('./api/storefront', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api/storefront')>()
  return {
    ...actual,
    listStorefrontCategories: vi.fn().mockResolvedValue([]),
    listStorefrontProducts: vi.fn().mockResolvedValue([]),
    getStorefrontProduct: vi.fn(),
  }
})

function renderAt(path: string) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

describe('App routing', () => {
  afterEach(() => {
    window.history.pushState({}, '', '/')
  })

  it('shows the customer Home page at "/"', async () => {
    renderAt('/')
    expect(await screen.findByRole('link', { name: 'Shop Now' })).toBeInTheDocument()
  })

  it('customer header shows Home/Shop nav and the store name, never admin tool names', async () => {
    renderAt('/')
    await screen.findByRole('banner')
    const header = screen.getByRole('banner')

    expect(within(header).getByText('Wehbi Nuts')).toBeInTheDocument()
    expect(within(header).getByRole('link', { name: 'Home' })).toBeInTheDocument()
    expect(within(header).getByRole('link', { name: 'Shop' })).toBeInTheDocument()
    expect(within(header).queryByText('Digitizer')).not.toBeInTheDocument()
    expect(within(header).queryByText('Review')).not.toBeInTheDocument()
    expect(within(header).queryByText('Catalog')).not.toBeInTheDocument()
  })

  it('renders the Shop page at "/shop"', async () => {
    renderAt('/shop')
    expect(await screen.findByRole('heading', { name: 'Shop' })).toBeInTheDocument()
  })

  it('renders the admin Digitizer tool at "/admin/digitizer"', async () => {
    renderAt('/admin/digitizer')
    expect(await screen.findByText('AI Product Digitizer')).toBeInTheDocument()
  })

  it('renders the admin Review tool at "/admin/review"', async () => {
    renderAt('/admin/review')
    expect(await screen.findByRole('heading', { name: 'Review' })).toBeInTheDocument()
  })

  it('renders the admin Catalog tool at "/admin/catalog"', async () => {
    renderAt('/admin/catalog')
    expect(await screen.findByRole('heading', { name: 'Catalog' })).toBeInTheDocument()
  })

  it('"/admin" redirects to the Digitizer tool', async () => {
    renderAt('/admin')
    expect(await screen.findByText('AI Product Digitizer')).toBeInTheDocument()
  })

  it('admin nav never shows customer storefront links', async () => {
    renderAt('/admin/digitizer')
    await screen.findByText('AI Product Digitizer')
    const adminNav = screen.getByRole('navigation', { name: 'Admin' })

    expect(within(adminNav).getByText('Digitizer')).toBeInTheDocument()
    expect(within(adminNav).getByText('Review')).toBeInTheDocument()
    expect(within(adminNav).getByText('Catalog')).toBeInTheDocument()
    expect(within(adminNav).queryByText('Shop')).not.toBeInTheDocument()
    expect(within(adminNav).queryByText('Home')).not.toBeInTheDocument()
  })

  it('shows a 404 page for an unknown route', async () => {
    renderAt('/this-page-does-not-exist')
    expect(await screen.findByText('Page not found')).toBeInTheDocument()
  })

  it('renders the Cart placeholder page without pretending checkout works', async () => {
    renderAt('/cart')
    expect(await screen.findByText('Your cart is empty')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /checkout/i })).not.toBeInTheDocument()
  })
})
