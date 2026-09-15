import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { HeroSlideshow } from './HeroSlideshow'

function mockReducedMotion(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('reduce') ? matches : false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

function dominantSrc(container: HTMLElement): string | null {
  const dominant = container.querySelector('[data-slot="dominant"] img')
  return dominant ? dominant.getAttribute('src') : null
}

describe('HeroSlideshow', () => {
  beforeEach(() => {
    mockReducedMotion(false)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders all four local hero images as one decorative visual region', () => {
    const { container } = render(<HeroSlideshow />)

    const images = container.querySelectorAll('img')
    expect(images).toHaveLength(4)
    for (const image of images) {
      expect(image.getAttribute('src')).toMatch(/hero-slideshow/)
      // Decorative -- the composition itself carries one collective label.
      expect(image.getAttribute('alt')).toBe('')
    }
    expect(screen.getByRole('img', { name: /coffee, nuts, and spices/i })).toBeInTheDocument()
  })

  it('starts with exactly one dominant photo and the rest layered behind it', () => {
    const { container } = render(<HeroSlideshow />)

    expect(container.querySelectorAll('[data-slot="dominant"]')).toHaveLength(1)
    expect(container.querySelectorAll('[data-slot="right"]')).toHaveLength(1)
    expect(container.querySelectorAll('[data-slot="left"]')).toHaveLength(1)
    expect(container.querySelectorAll('[data-slot="offstage"]')).toHaveLength(1)
  })

  it('automatically reshuffles which photo is dominant, looping through all four', () => {
    vi.useFakeTimers()
    const { container } = render(<HeroSlideshow />)

    const firstDominant = dominantSrc(container)
    expect(firstDominant).not.toBeNull()

    act(() => vi.advanceTimersByTime(4200))
    const secondDominant = dominantSrc(container)
    expect(secondDominant).not.toBe(firstDominant)

    act(() => vi.advanceTimersByTime(4200))
    const thirdDominant = dominantSrc(container)
    expect(thirdDominant).not.toBe(secondDominant)
    expect(thirdDominant).not.toBe(firstDominant)

    act(() => vi.advanceTimersByTime(4200))
    const fourthDominant = dominantSrc(container)

    // All four distinct so far; the fifth tick must loop back to the first.
    act(() => vi.advanceTimersByTime(4200))
    expect(dominantSrc(container)).toBe(firstDominant)
    expect(new Set([firstDominant, secondDominant, thirdDominant, fourthDominant]).size).toBe(4)
  })

  it('never renders slideshow arrows, dots, tabs, or caption text', () => {
    const { container } = render(<HeroSlideshow />)

    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    expect(screen.queryAllByRole('tab')).toHaveLength(0)
    expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /previous/i })).not.toBeInTheDocument()
    expect(container.querySelectorAll('button')).toHaveLength(0)
  })
})
