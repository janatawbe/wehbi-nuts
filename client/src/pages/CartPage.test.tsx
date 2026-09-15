import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { CartProvider } from '../cart/CartContext'
import type { CartItem } from '../cart/cartTypes'
import { LanguageProvider } from '../i18n/LanguageContext'
import { CartPage } from './CartPage'

const CART_STORAGE_KEY = 'wehbi-nuts-cart'
const LANGUAGE_STORAGE_KEY = 'wehbi-nuts-storefront-language'

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

const UNIT_ITEM: CartItem = {
  productId: 'p-unit',
  nameEn: 'Chocolate Bites',
  nameAr: 'قطع شوكولاتة',
  image: null,
  sellingMode: 'unit',
  unitPriceSnapshot: '5.00',
  packageWeightSnapshot: '0.200',
  quantity: 2,
  weightGrams: null,
}

function seedCart(items: CartItem[]) {
  window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(items))
}

function renderCartPage() {
  return render(
    <LanguageProvider>
      <CartProvider>
        <MemoryRouter>
          <CartPage />
        </MemoryRouter>
      </CartProvider>
    </LanguageProvider>,
  )
}

describe('CartPage', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('shows an empty-cart state with a link back to the shop', () => {
    renderCartPage()

    expect(screen.getByText('Your cart is empty')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Continue Shopping' })).toHaveAttribute('href', '/shop')
  })

  it('shows each cart line with name, price, and subtotal', () => {
    seedCart([WEIGHT_ITEM, UNIT_ITEM])
    renderCartPage()

    expect(screen.getByText('Roasted Pistachios')).toBeInTheDocument()
    expect(screen.getByText('Chocolate Bites')).toBeInTheDocument()
    expect(screen.getByText('$6.00')).toBeInTheDocument() // 20.00/kg * 0.3kg
    expect(screen.getByText('$10.00')).toBeInTheDocument() // 5.00 * 2
  })

  it('shows the order total summed across all lines', () => {
    seedCart([WEIGHT_ITEM, UNIT_ITEM])
    renderCartPage()

    expect(screen.getByText('Order Total')).toBeInTheDocument()
    expect(screen.getByText('$16.00')).toBeInTheDocument()
  })

  it('removes a line item', () => {
    seedCart([WEIGHT_ITEM])
    renderCartPage()

    fireEvent.click(screen.getByText('Remove'))

    expect(screen.getByText('Your cart is empty')).toBeInTheDocument()
  })

  it('changing the weight preset updates that line and the total', () => {
    seedCart([WEIGHT_ITEM])
    renderCartPage()

    fireEvent.click(screen.getByRole('button', { name: '1 kg' }))

    expect(screen.getAllByText('$20.00').length).toBeGreaterThan(0)
  })

  it('increasing a unit quantity updates that line and the total', () => {
    seedCart([UNIT_ITEM])
    renderCartPage()

    fireEvent.click(screen.getByRole('button', { name: 'Increase' }))

    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getAllByText('$15.00').length).toBeGreaterThan(0)
  })

  it('has a Checkout call to action', () => {
    seedCart([WEIGHT_ITEM])
    renderCartPage()

    expect(screen.getByRole('button', { name: 'Checkout' })).toBeInTheDocument()
  })

  it('shows Arabic names and translated labels when Arabic is active', () => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, 'ar')
    seedCart([WEIGHT_ITEM])

    renderCartPage()

    expect(screen.getByText('فستق محمص')).toBeInTheDocument()
    expect(screen.getByText('إجمالي الطلب')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'إتمام الطلب' })).toBeInTheDocument()
  })
})
