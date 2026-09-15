import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { LanguageProvider } from '../i18n/LanguageContext'
import type { CheckoutResult } from '../types/checkout'
import { OrderSuccessPage } from './OrderSuccessPage'

const RESULT: CheckoutResult = {
  id: 'order-1',
  order_number: 'WNABCDEF12',
  status: 'pending',
  subtotal: '16.00',
  total: '16.00',
  items: [
    {
      product_id: 'p1',
      product_name: 'Roasted Pistachios',
      product_name_ar: 'فستق محمص',
      selling_mode: 'weight',
      quantity: '0.300',
      unit_price: '20.00',
      line_total: '6.00',
      package_weight: null,
    },
    {
      product_id: 'p2',
      product_name: 'Chocolate Bites',
      product_name_ar: null,
      selling_mode: 'unit',
      quantity: '2',
      unit_price: '5.00',
      line_total: '10.00',
      package_weight: '0.200',
    },
  ],
}

function renderWithState(state: unknown) {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[{ pathname: '/order/success', state }]}>
        <Routes>
          <Route path="/order/success" element={<OrderSuccessPage />} />
          <Route path="/shop" element={<p>Shop page</p>} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

describe('OrderSuccessPage', () => {
  it('shows the order number, summary, and Cash on Delivery notice when valid state is present', () => {
    renderWithState({ result: RESULT })

    expect(screen.getByText('Order Confirmed!')).toBeInTheDocument()
    expect(screen.getByText('WNABCDEF12')).toBeInTheDocument()
    expect(screen.getByText('Roasted Pistachios')).toBeInTheDocument()
    expect(screen.getByText('Chocolate Bites')).toBeInTheDocument()
    expect(screen.getByText('$16.00')).toBeInTheDocument()
    expect(screen.getByText('Cash on Delivery')).toBeInTheDocument()
    expect(screen.getByText("You'll pay in cash when your order is delivered.")).toBeInTheDocument()
  })

  it('shows a graceful fallback with no navigation state (e.g. a direct visit or refresh)', () => {
    renderWithState(undefined)

    expect(screen.getByTestId('order-success-invalid')).toBeInTheDocument()
    expect(screen.getByText('No order to show')).toBeInTheDocument()
    expect(screen.queryByText('WNABCDEF12')).not.toBeInTheDocument()
  })

  it('the fallback state provides a way back to the shop', () => {
    renderWithState(undefined)

    const link = screen.getByRole('link', { name: 'Continue Shopping' })
    expect(link).toHaveAttribute('href', '/shop')
  })

  it('shows a graceful fallback for malformed navigation state', () => {
    renderWithState({ result: { not: 'a real checkout result' } })

    expect(screen.getByTestId('order-success-invalid')).toBeInTheDocument()
  })

  it('shows the Arabic product name when Arabic is active (regression)', () => {
    window.localStorage.setItem('wehbi-nuts-storefront-language', 'ar')
    renderWithState({ result: RESULT })

    expect(screen.getByText('فستق محمص')).toBeInTheDocument()
    expect(screen.queryByText('Roasted Pistachios')).not.toBeInTheDocument()
    window.localStorage.removeItem('wehbi-nuts-storefront-language')
  })

  it('falls back to the English product name in Arabic mode when the Arabic snapshot is missing', () => {
    window.localStorage.setItem('wehbi-nuts-storefront-language', 'ar')
    renderWithState({ result: RESULT })

    expect(screen.getByText('Chocolate Bites')).toBeInTheDocument()
    window.localStorage.removeItem('wehbi-nuts-storefront-language')
  })
})
