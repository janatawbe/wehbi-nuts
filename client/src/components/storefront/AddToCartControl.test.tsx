import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { CartProvider, useCart } from '../../cart/CartContext'
import type { StorefrontProduct } from '../../types/storefront'
import { AddToCartControl } from './AddToCartControl'

function makeProduct(overrides: Partial<StorefrontProduct> = {}): StorefrontProduct {
  return {
    id: 'p1',
    name_en: 'Roasted Almonds',
    name_ar: 'لوز محمص',
    description_en: null,
    description_ar: null,
    brand: null,
    category: null,
    selling_mode: 'weight',
    package_weight: null,
    price: '20.00',
    stock_status: 'in_stock',
    image: null,
    ...overrides,
  }
}

function CartSpy() {
  const { items } = useCart()
  return <div data-testid="cart-items">{JSON.stringify(items)}</div>
}

function renderControl(product: StorefrontProduct, variant: 'compact' | 'full' = 'compact') {
  return render(
    <CartProvider>
      <AddToCartControl product={product} variant={variant} />
      <CartSpy />
    </CartProvider>,
  )
}

describe('AddToCartControl', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('compact variant adds the smallest quick weight with one click', () => {
    renderControl(makeProduct({ selling_mode: 'weight' }), 'compact')

    fireEvent.click(screen.getByRole('button', { name: /add to cart/i }))

    const items = JSON.parse(screen.getByTestId('cart-items').textContent ?? '[]')
    expect(items).toHaveLength(1)
    expect(items[0].weightGrams).toBe(100)
  })

  it('compact variant adds quantity 1 for a unit product', () => {
    renderControl(makeProduct({ selling_mode: 'unit' }), 'compact')

    fireEvent.click(screen.getByRole('button', { name: /add to cart/i }))

    const items = JSON.parse(screen.getByTestId('cart-items').textContent ?? '[]')
    expect(items[0].quantity).toBe(1)
  })

  it('compact variant is disabled for an out-of-stock product', () => {
    renderControl(makeProduct({ stock_status: 'out_of_stock' }), 'compact')

    expect(screen.getByRole('button', { name: /add to cart/i })).toBeDisabled()
  })

  it('compact variant shows a brief "Added" confirmation after a click', () => {
    renderControl(makeProduct({ selling_mode: 'weight' }), 'compact')

    fireEvent.click(screen.getByRole('button', { name: /add to cart/i }))

    expect(screen.getByRole('button', { name: /added/i })).toBeInTheDocument()
  })

  it('full variant shows quick weight chips with grams/kg labels only, never "oz", and no fixed maximum', () => {
    renderControl(makeProduct({ selling_mode: 'weight' }), 'full')

    const labels = ['100 g', '250 g', '500 g', '1 kg']
    for (const label of labels) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    expect(labels.join(' ')).not.toMatch(/oz|ounce/i)
  })

  it('full variant adds the selected quick weight', () => {
    renderControl(makeProduct({ selling_mode: 'weight' }), 'full')

    fireEvent.click(screen.getByRole('button', { name: '500 g' }))
    fireEvent.click(screen.getByRole('button', { name: /add to cart/i }))

    const items = JSON.parse(screen.getByTestId('cart-items').textContent ?? '[]')
    expect(items[0].weightGrams).toBe(500)
  })

  it('full variant defaults the amount box to 100 (grams)', () => {
    renderControl(makeProduct({ selling_mode: 'weight' }), 'full')

    expect(screen.getByLabelText('Weight')).toHaveValue(100)
  })

  it('full variant lets the customer type any direct amount with no upper bound (e.g. 3 kg)', () => {
    renderControl(makeProduct({ selling_mode: 'weight' }), 'full')

    fireEvent.click(screen.getByRole('button', { name: 'kg' }))
    fireEvent.change(screen.getByLabelText('Weight'), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: /add to cart/i }))

    const items = JSON.parse(screen.getByTestId('cart-items').textContent ?? '[]')
    expect(items[0].weightGrams).toBe(3000)
  })

  it('full variant supports a decimal kilogram amount (1.5 kg)', () => {
    renderControl(makeProduct({ selling_mode: 'weight' }), 'full')

    fireEvent.click(screen.getByRole('button', { name: 'kg' }))
    fireEvent.change(screen.getByLabelText('Weight'), { target: { value: '1.5' } })
    fireEvent.click(screen.getByRole('button', { name: /add to cart/i }))

    const items = JSON.parse(screen.getByTestId('cart-items').textContent ?? '[]')
    expect(items[0].weightGrams).toBe(1500)
  })

  it('full variant supports a direct gram amount (750 g)', () => {
    renderControl(makeProduct({ selling_mode: 'weight' }), 'full')

    fireEvent.change(screen.getByLabelText('Weight'), { target: { value: '750' } })
    fireEvent.click(screen.getByRole('button', { name: /add to cart/i }))

    const items = JSON.parse(screen.getByTestId('cart-items').textContent ?? '[]')
    expect(items[0].weightGrams).toBe(750)
  })

  it('shows the live calculated price as the weight changes', () => {
    renderControl(makeProduct({ selling_mode: 'weight', price: '20.00' }), 'full')

    fireEvent.change(screen.getByLabelText('Weight'), { target: { value: '300' } })

    expect(screen.getByText('$6.00')).toBeInTheDocument()
  })

  it('rejects zero and disables Add to Cart until a valid weight is entered', () => {
    renderControl(makeProduct({ selling_mode: 'weight' }), 'full')

    fireEvent.change(screen.getByLabelText('Weight'), { target: { value: '0' } })

    expect(screen.getByRole('alert')).toHaveTextContent('Enter a weight greater than 0.')
    expect(screen.getByRole('button', { name: /add to cart/i })).toBeDisabled()
  })

  it('rejects a negative weight', () => {
    renderControl(makeProduct({ selling_mode: 'weight' }), 'full')

    fireEvent.change(screen.getByLabelText('Weight'), { target: { value: '-5' } })

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add to cart/i })).toBeDisabled()
  })

  it('full variant shows a small "Added to cart" confirmation after adding', () => {
    renderControl(makeProduct({ selling_mode: 'weight' }), 'full')

    fireEvent.click(screen.getByRole('button', { name: /add to cart/i }))

    expect(screen.getByText('Added to cart')).toBeInTheDocument()
  })

  it('full variant shows a quantity stepper for a unit product and adds the selected count', () => {
    renderControl(makeProduct({ selling_mode: 'unit' }), 'full')

    fireEvent.click(screen.getByRole('button', { name: 'Increase' }))
    fireEvent.click(screen.getByRole('button', { name: 'Increase' }))
    fireEvent.click(screen.getByRole('button', { name: /add to cart/i }))

    const items = JSON.parse(screen.getByTestId('cart-items').textContent ?? '[]')
    expect(items[0].quantity).toBe(3)
  })

  it('full variant quantity stepper never goes below 1', () => {
    renderControl(makeProduct({ selling_mode: 'unit' }), 'full')

    expect(screen.getByRole('button', { name: 'Decrease' })).toBeDisabled()
  })

  it('full variant is fully disabled for an out-of-stock product', () => {
    renderControl(makeProduct({ selling_mode: 'weight', stock_status: 'out_of_stock' }), 'full')

    expect(screen.getByRole('button', { name: '100 g' })).toBeDisabled()
    expect(screen.getByRole('button', { name: /add to cart/i })).toBeDisabled()
  })
})
