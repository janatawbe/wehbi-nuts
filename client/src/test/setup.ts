import '@testing-library/jest-dom/vitest'

// jsdom has no IntersectionObserver -- needed by framer-motion's
// `whileInView` (used for restrained on-scroll reveals in the storefront,
// see components/storefront). A minimal stub is enough: tests never rely
// on the observer actually firing, only on the tree rendering without
// crashing.
if (typeof globalThis.IntersectionObserver === 'undefined') {
  class MockIntersectionObserver {
    readonly root: Element | Document | null = null
    readonly rootMargin: string = ''
    readonly scrollMargin: string = ''
    readonly thresholds: ReadonlyArray<number> = []
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords(): IntersectionObserverEntry[] {
      return []
    }
  }
  globalThis.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver
}
