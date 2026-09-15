import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { LanguageProvider, useLanguage } from './LanguageContext'

const STORAGE_KEY = 'wehbi-nuts-storefront-language'

function Probe() {
  const { language, direction, t, setLanguage, toggleLanguage } = useLanguage()
  return (
    <div>
      <p data-testid="language">{language}</p>
      <p data-testid="direction">{direction}</p>
      <p data-testid="translated">{t('nav.home')}</p>
      <button onClick={() => setLanguage('ar')}>set-ar</button>
      <button onClick={() => setLanguage('en')}>set-en</button>
      <button onClick={toggleLanguage}>toggle</button>
    </div>
  )
}

function renderProbe() {
  return render(
    <LanguageProvider>
      <Probe />
    </LanguageProvider>,
  )
}

describe('LanguageContext', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('defaults to English/LTR with no stored preference', () => {
    renderProbe()

    expect(screen.getByTestId('language')).toHaveTextContent('en')
    expect(screen.getByTestId('direction')).toHaveTextContent('ltr')
    expect(screen.getByTestId('translated')).toHaveTextContent('Home')
  })

  it('switches English to Arabic and updates direction and translations', () => {
    renderProbe()

    fireEvent.click(screen.getByText('set-ar'))

    expect(screen.getByTestId('language')).toHaveTextContent('ar')
    expect(screen.getByTestId('direction')).toHaveTextContent('rtl')
    expect(screen.getByTestId('translated')).toHaveTextContent('الرئيسية')
  })

  it('switches Arabic back to English', () => {
    renderProbe()
    fireEvent.click(screen.getByText('set-ar'))
    fireEvent.click(screen.getByText('set-en'))

    expect(screen.getByTestId('language')).toHaveTextContent('en')
    expect(screen.getByTestId('direction')).toHaveTextContent('ltr')
  })

  it('toggleLanguage flips between the two languages', () => {
    renderProbe()

    fireEvent.click(screen.getByText('toggle'))
    expect(screen.getByTestId('language')).toHaveTextContent('ar')

    fireEvent.click(screen.getByText('toggle'))
    expect(screen.getByTestId('language')).toHaveTextContent('en')
  })

  it('persists the selected language to localStorage', () => {
    renderProbe()
    fireEvent.click(screen.getByText('set-ar'))

    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('ar')
  })

  it('reads a previously-persisted language back on mount (survives refresh/reopen)', () => {
    window.localStorage.setItem(STORAGE_KEY, 'ar')

    renderProbe()

    expect(screen.getByTestId('language')).toHaveTextContent('ar')
    expect(screen.getByTestId('direction')).toHaveTextContent('rtl')
  })

  it('ignores a garbage stored value and falls back to English', () => {
    window.localStorage.setItem(STORAGE_KEY, 'fr')

    renderProbe()

    expect(screen.getByTestId('language')).toHaveTextContent('en')
  })

  it('provides working English translations even with no LanguageProvider present', () => {
    render(<Probe />)

    expect(screen.getByTestId('language')).toHaveTextContent('en')
    expect(screen.getByTestId('direction')).toHaveTextContent('ltr')
    expect(screen.getByTestId('translated')).toHaveTextContent('Home')
  })
})
