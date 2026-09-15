import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as checkoutApi from '../api/checkout'
import { StorefrontApiError } from '../api/storefront'
import { CartProvider } from '../cart/CartContext'
import type { CartItem } from '../cart/cartTypes'
import { LanguageProvider } from '../i18n/LanguageContext'
import type { CheckoutResult } from '../types/checkout'
import { CheckoutPage } from './CheckoutPage'

vi.mock('../api/checkout', () => ({
  submitCheckout: vi.fn(),
}))

const CART_STORAGE_KEY = 'wehbi-nuts-cart'

const WEIGHT_ITEM: CartItem = {
  productId: 'p-weight',
  nameEn: 'Roasted Pistachios',
  nameAr: 'فستق محمص',
  image: null,
  sellingMode: 'weight',
  unitPriceSnapshot: '20.00',
  packageWeightSnapshot: null,
  quantity: null,
  weightGrams: 300,
}

function seedCart(items: CartItem[]) {
  window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(items))
}

function SuccessProbe() {
  const location = useLocation()
  const result = (location.state as { result?: CheckoutResult } | null)?.result
  return <p data-testid="success-probe">{result ? result.order_number : 'no-result'}</p>
}

function renderCheckout() {
  return render(
    <LanguageProvider>
      <CartProvider>
        <MemoryRouter initialEntries={['/checkout']}>
          <Routes>
            <Route path="/checkout" element={<CheckoutPage />} />
            <Route path="/order/success" element={<SuccessProbe />} />
          </Routes>
        </MemoryRouter>
      </CartProvider>
    </LanguageProvider>,
  )
}

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText('Full Name'), { target: { value: 'Jana Tawbe' } })
  fireEvent.change(screen.getByLabelText('Phone Number'), { target: { value: '+96170000000' } })
  fireEvent.change(screen.getByLabelText('Delivery Address'), { target: { value: 'Building 4, Hamra Street' } })
  fireEvent.change(screen.getByLabelText('Area / Neighborhood'), { target: { value: 'Hamra' } })
}

const SUCCESS_RESULT: CheckoutResult = {
  id: 'order-1',
  order_number: 'WNABCDEF12',
  status: 'pending',
  subtotal: '6.00',
  total: '6.00',
  items: [
    {
      product_id: 'p-weight',
      product_name: 'Roasted Pistachios',
      product_name_ar: 'فستق محمص',
      selling_mode: 'weight',
      quantity: '0.300',
      unit_price: '20.00',
      line_total: '6.00',
      package_weight: null,
    },
  ],
}

describe('CheckoutPage', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.mocked(checkoutApi.submitCheckout).mockReset()
  })

  it('shows an empty-cart message and no form when the cart is empty', () => {
    renderCheckout()

    expect(screen.getByText('Your cart is empty. Add something from the shop before checking out.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Full Name')).not.toBeInTheDocument()
  })

  it('clearly shows Cash on Delivery as the payment method', () => {
    seedCart([WEIGHT_ITEM])
    renderCheckout()

    expect(screen.getByText('Payment Method')).toBeInTheDocument()
    expect(screen.getByText('Cash on Delivery')).toBeInTheDocument()
  })

  it('shows an order summary matching the cart', () => {
    seedCart([WEIGHT_ITEM])
    renderCheckout()

    expect(screen.getByText('Order Summary')).toBeInTheDocument()
    expect(screen.getByText('Roasted Pistachios')).toBeInTheDocument()
    expect(screen.getAllByText('$6.00').length).toBeGreaterThan(0)
  })

  it('shows the Arabic product name in the order summary when Arabic is active (regression)', () => {
    window.localStorage.setItem('wehbi-nuts-storefront-language', 'ar')
    seedCart([WEIGHT_ITEM])
    renderCheckout()

    expect(screen.getByText('فستق محمص')).toBeInTheDocument()
    expect(screen.queryByText('Roasted Pistachios')).not.toBeInTheDocument()
  })

  it('rejects submission with required fields empty, and never calls the API', async () => {
    seedCart([WEIGHT_ITEM])
    renderCheckout()

    fireEvent.click(screen.getByRole('button', { name: 'Place Order' }))

    expect(await screen.findAllByText('This field is required.')).toHaveLength(4)
    expect(checkoutApi.submitCheckout).not.toHaveBeenCalled()
  })

  it('submits the correct payload shape with no price fields at all', async () => {
    seedCart([WEIGHT_ITEM])
    vi.mocked(checkoutApi.submitCheckout).mockResolvedValue(SUCCESS_RESULT)
    renderCheckout()
    fillRequiredFields()

    fireEvent.click(screen.getByRole('button', { name: 'Place Order' }))

    await waitFor(() => expect(checkoutApi.submitCheckout).toHaveBeenCalledTimes(1))
    const payload = vi.mocked(checkoutApi.submitCheckout).mock.calls[0][0]
    expect(payload).toEqual({
      customer_name: 'Jana Tawbe',
      customer_phone: '+96170000000',
      delivery_address: 'Building 4, Hamra Street',
      delivery_area: 'Hamra',
      notes: null,
      items: [{ product_id: 'p-weight', selling_mode: 'weight', weight_grams: 300 }],
    })
    expect(JSON.stringify(payload)).not.toMatch(/price|total|subtotal/i)
  })

  it('on success, navigates to the order-success page carrying the server result, and clears the cart', async () => {
    seedCart([WEIGHT_ITEM])
    vi.mocked(checkoutApi.submitCheckout).mockResolvedValue(SUCCESS_RESULT)
    renderCheckout()
    fillRequiredFields()

    fireEvent.click(screen.getByRole('button', { name: 'Place Order' }))

    expect(await screen.findByTestId('success-probe')).toHaveTextContent('WNABCDEF12')
    expect(window.localStorage.getItem(CART_STORAGE_KEY)).toBe('[]')
  })

  it('on API failure, shows an error and leaves the cart completely intact', async () => {
    seedCart([WEIGHT_ITEM])
    vi.mocked(checkoutApi.submitCheckout).mockRejectedValue(new StorefrontApiError('Product is out of stock.', 422))
    renderCheckout()
    fillRequiredFields()

    fireEvent.click(screen.getByRole('button', { name: 'Place Order' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Product is out of stock.')
    expect(screen.queryByTestId('success-probe')).not.toBeInTheDocument()
    const stored = JSON.parse(window.localStorage.getItem(CART_STORAGE_KEY) ?? '[]')
    expect(stored).toHaveLength(1)
  })

  it('disables the submit button while the request is in flight', async () => {
    seedCart([WEIGHT_ITEM])
    let resolvePromise: (value: CheckoutResult) => void = () => {}
    vi.mocked(checkoutApi.submitCheckout).mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve
      }),
    )
    renderCheckout()
    fillRequiredFields()

    fireEvent.click(screen.getByRole('button', { name: 'Place Order' }))

    expect(await screen.findByRole('button', { name: 'Placing your order...' })).toBeDisabled()
    resolvePromise(SUCCESS_RESULT)
  })
})
