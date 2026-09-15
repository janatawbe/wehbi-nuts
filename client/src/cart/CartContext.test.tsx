import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { CartProvider, useCart } from './CartContext'
import type { AddToCartInput } from './cartTypes'

const STORAGE_KEY = 'wehbi-nuts-cart'

const WEIGHT_PRODUCT: AddToCartInput = {
  productId: 'p-weight',
  nameEn: 'Roasted Pistachios',
  nameAr: 'فستق محمص',
  image: null,
  sellingMode: 'weight',
  unitPriceSnapshot: '20.00',
  packageWeightSnapshot: null,
  weightGrams: 300,
}

const UNIT_PRODUCT: AddToCartInput = {
  productId: 'p-unit',
  nameEn: 'Chocolate Bites',
  nameAr: 'قطع شوكولاتة',
  image: null,
  sellingMode: 'unit',
  unitPriceSnapshot: '5.00',
  packageWeightSnapshot: '0.200',
  quantity: 2,
}

function Probe() {
  const cart = useCart()
  return (
    <div>
      <p data-testid="item-count">{cart.itemCount}</p>
      <p data-testid="subtotal">{cart.subtotal.toFixed(2)}</p>
      <ul>
        {cart.items.map((item) => (
          <li key={item.productId} data-testid={`item-${item.productId}`}>
            {item.sellingMode === 'weight' ? item.weightGrams : item.quantity}
          </li>
        ))}
      </ul>
      <button onClick={() => cart.addItem(WEIGHT_PRODUCT)}>add-weight</button>
      <button onClick={() => cart.addItem(UNIT_PRODUCT)}>add-unit</button>
      <button onClick={() => cart.removeItem('p-weight')}>remove-weight</button>
      <button onClick={() => cart.increaseQuantity('p-unit')}>increase-unit</button>
      <button onClick={() => cart.decreaseQuantity('p-unit')}>decrease-unit</button>
      <button onClick={() => cart.setWeightGrams('p-weight', 500)}>set-weight-500</button>
      <button onClick={() => cart.setWeightGrams('p-weight', 2500)}>set-weight-2500</button>
      <button onClick={() => cart.setWeightGrams('p-weight', -50)}>set-weight-negative</button>
      <button onClick={() => cart.clearCart()}>clear</button>
    </div>
  )
}

function renderCart() {
  return render(
    <CartProvider>
      <Probe />
    </CartProvider>,
  )
}

describe('CartContext', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('starts empty with no stored cart', () => {
    renderCart()
    expect(screen.getByTestId('item-count')).toHaveTextContent('0')
  })

  it('adds a weight-mode item', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-weight'))

    expect(screen.getByTestId('item-count')).toHaveTextContent('1')
    expect(screen.getByTestId('item-p-weight')).toHaveTextContent('300')
  })

  it('adds a unit-mode item', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-unit'))

    expect(screen.getByTestId('item-p-unit')).toHaveTextContent('2')
  })

  it('never creates a duplicate line for the same product', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-weight'))
    fireEvent.click(screen.getByText('add-weight'))

    expect(screen.getByTestId('item-count')).toHaveTextContent('1')
  })

  it('adding a weight item already in the cart increases it by one step (100g), not a preset jump', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-weight')) // 300g
    fireEvent.click(screen.getByText('add-weight')) // -> +100g = 400g

    expect(screen.getByTestId('item-p-weight')).toHaveTextContent('400')
  })

  it('sets a weight item to any positive amount, including several kilograms', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-weight'))
    fireEvent.click(screen.getByText('set-weight-2500'))

    expect(screen.getByTestId('item-p-weight')).toHaveTextContent('2500')
  })

  it('setWeightGrams rejects a negative value by flooring at the minimum', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-weight'))
    fireEvent.click(screen.getByText('set-weight-negative'))

    expect(screen.getByTestId('item-p-weight')).toHaveTextContent('100')
  })

  it('adding a unit item already in the cart increases its quantity', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-unit')) // quantity 2
    fireEvent.click(screen.getByText('add-unit')) // +2 more

    expect(screen.getByTestId('item-p-unit')).toHaveTextContent('4')
  })

  it('removes an item', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-weight'))
    fireEvent.click(screen.getByText('remove-weight'))

    expect(screen.getByTestId('item-count')).toHaveTextContent('0')
  })

  it('increases and decreases a unit item quantity', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-unit'))
    fireEvent.click(screen.getByText('increase-unit'))
    expect(screen.getByTestId('item-p-unit')).toHaveTextContent('3')

    fireEvent.click(screen.getByText('decrease-unit'))
    expect(screen.getByTestId('item-p-unit')).toHaveTextContent('2')
  })

  it('never decreases a unit quantity below 1', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-unit'))
    fireEvent.click(screen.getByText('decrease-unit'))
    fireEvent.click(screen.getByText('decrease-unit'))
    fireEvent.click(screen.getByText('decrease-unit'))

    expect(screen.getByTestId('item-p-unit')).toHaveTextContent('1')
  })

  it('sets a weight item to a specific preset', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-weight'))
    fireEvent.click(screen.getByText('set-weight-500'))

    expect(screen.getByTestId('item-p-weight')).toHaveTextContent('500')
  })

  it('computes a display subtotal across mixed weight and unit lines', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-weight')) // 20.00/kg * 0.3kg = 6.00
    fireEvent.click(screen.getByText('add-unit')) // 5.00 * 2 = 10.00

    expect(screen.getByTestId('subtotal')).toHaveTextContent('16.00')
  })

  it('clears the cart', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-weight'))
    fireEvent.click(screen.getByText('add-unit'))
    fireEvent.click(screen.getByText('clear'))

    expect(screen.getByTestId('item-count')).toHaveTextContent('0')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('[]')
  })

  it('persists the cart to localStorage', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-weight'))

    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '[]')
    expect(stored).toHaveLength(1)
    expect(stored[0].productId).toBe('p-weight')
  })

  it('restores a previously-persisted cart on remount (survives refresh)', () => {
    const { unmount } = renderCart()
    fireEvent.click(screen.getByText('add-weight'))
    unmount()

    renderCart()

    expect(screen.getByTestId('item-count')).toHaveTextContent('1')
  })

  it('never stores customer/checkout information -- only product/quantity fields', () => {
    renderCart()
    fireEvent.click(screen.getByText('add-weight'))

    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '[]')
    const keys = Object.keys(stored[0])
    for (const forbidden of ['customerName', 'customerPhone', 'deliveryAddress', 'deliveryArea', 'notes']) {
      expect(keys).not.toContain(forbidden)
    }
  })

  it('works with no CartProvider present (safe default context)', () => {
    render(<Probe />)
    expect(screen.getByTestId('item-count')).toHaveTextContent('0')
  })
})
