import { beforeEach, describe, expect, it } from 'vitest'
import { clearCartStorage, readCartFromStorage, writeCartToStorage } from './cartStorage'
import type { CartItem } from './cartTypes'

const STORAGE_KEY = 'wehbi-nuts-cart'

const VALID_ITEM: CartItem = {
  productId: 'p1',
  nameEn: 'Roasted Almonds',
  nameAr: 'لوز محمص',
  image: null,
  sellingMode: 'weight',
  unitPriceSnapshot: '20.00',
  packageWeightSnapshot: null,
  quantity: null,
  weightGrams: 300,
}

describe('cartStorage', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('returns an empty array when nothing is stored', () => {
    expect(readCartFromStorage()).toEqual([])
  })

  it('round-trips a valid cart', () => {
    writeCartToStorage([VALID_ITEM])
    expect(readCartFromStorage()).toEqual([VALID_ITEM])
  })

  it('clears the stored cart', () => {
    writeCartToStorage([VALID_ITEM])
    clearCartStorage()
    expect(readCartFromStorage()).toEqual([])
  })

  it('ignores non-JSON garbage without throwing', () => {
    window.localStorage.setItem(STORAGE_KEY, 'not json at all {{{')
    expect(readCartFromStorage()).toEqual([])
  })

  it('ignores a stored value that is not an array', () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ not: 'an array' }))
    expect(readCartFromStorage()).toEqual([])
  })

  it('drops individual entries that do not match the expected shape', () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([VALID_ITEM, { productId: 'broken' }, { ...VALID_ITEM, productId: 'p2', sellingMode: 'bogus' }]),
    )

    expect(readCartFromStorage()).toEqual([VALID_ITEM])
  })
})
