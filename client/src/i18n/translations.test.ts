import { describe, expect, it } from 'vitest'
import { TRANSLATIONS, forwardArrow, localizedField } from './translations'

describe('localizedField', () => {
  it('returns the English field when the language is English', () => {
    expect(localizedField('Nuts', 'مكسرات', 'en')).toBe('Nuts')
  })

  it('returns the Arabic field when the language is Arabic and it is present', () => {
    expect(localizedField('Nuts', 'مكسرات', 'ar')).toBe('مكسرات')
  })

  it('falls back to English when the Arabic field is null', () => {
    expect(localizedField('Nuts', null, 'ar')).toBe('Nuts')
  })

  it('falls back to English when the Arabic field is undefined', () => {
    expect(localizedField('Nuts', undefined, 'ar')).toBe('Nuts')
  })

  it('falls back to English when the Arabic field is empty/whitespace-only', () => {
    expect(localizedField('Nuts', '   ', 'ar')).toBe('Nuts')
  })

  it('preserves a null English value when there is no Arabic override', () => {
    expect(localizedField(null, null, 'en')).toBeNull()
    expect(localizedField(null, null, 'ar')).toBeNull()
  })
})

describe('forwardArrow', () => {
  it('points right for LTR', () => {
    expect(forwardArrow('ltr')).toBe('→')
  })

  it('points left for RTL', () => {
    expect(forwardArrow('rtl')).toBe('←')
  })
})

describe('TRANSLATIONS', () => {
  it('has an identical key set for English and Arabic (no missing translations)', () => {
    const enKeys = Object.keys(TRANSLATIONS.en).sort()
    const arKeys = Object.keys(TRANSLATIONS.ar).sort()
    expect(arKeys).toEqual(enKeys)
  })

  it('never leaves an Arabic value blank', () => {
    for (const [key, value] of Object.entries(TRANSLATIONS.ar)) {
      expect(value.trim().length, `ar['${key}'] should not be blank`).toBeGreaterThan(0)
    }
  })
})
