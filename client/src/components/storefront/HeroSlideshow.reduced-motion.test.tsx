import { act, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { HeroSlideshow } from './HeroSlideshow'

// A dedicated file: framer-motion's useReducedMotion lazily reads
// `matchMedia` exactly once per module lifetime (see framer-motion's
// use-reduced-motion.mjs / motion-dom's reduced-motion state module) and
// caches the result -- it does not re-check on every render. Mocking
// `matchMedia` to "reduce" BEFORE this file's very first render is what
// makes that one-time read pick up the reduced-motion preference; mixing
// reduced- and normal-motion cases in the same file/module registry as
// HeroSlideshow.test.tsx would only ever observe whichever case rendered
// first.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  configurable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('reduce'),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

function dominantSrc(container: HTMLElement): string | null {
  const dominant = container.querySelector('[data-slot="dominant"] img')
  return dominant ? dominant.getAttribute('src') : null
}

describe('HeroSlideshow with prefers-reduced-motion', () => {
  it('does not auto-reshuffle', () => {
    vi.useFakeTimers()
    const { container } = render(<HeroSlideshow />)

    const initialDominant = dominantSrc(container)
    act(() => vi.advanceTimersByTime(30000))

    expect(dominantSrc(container)).toBe(initialDominant)
    vi.useRealTimers()
  })

  it('still renders a complete static collage, not a blank/broken state', () => {
    const { container } = render(<HeroSlideshow />)

    expect(container.querySelectorAll('img')).toHaveLength(4)
    expect(container.querySelector('[data-slot="dominant"]')).not.toBeNull()
    expect(container.querySelector('[data-slot="right"]')).not.toBeNull()
    expect(container.querySelector('[data-slot="left"]')).not.toBeNull()
  })
})
