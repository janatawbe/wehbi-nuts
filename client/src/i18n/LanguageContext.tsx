import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  DIRECTION_BY_LANGUAGE,
  TRANSLATIONS,
  type Direction,
  type Language,
  type TranslateFn,
  type TranslationKey,
} from './translations'

const STORAGE_KEY = 'wehbi-nuts-storefront-language'

interface LanguageContextValue {
  language: Language
  direction: Direction
  setLanguage: (language: Language) => void
  toggleLanguage: () => void
  t: TranslateFn
}

function isLanguage(value: unknown): value is Language {
  return value === 'en' || value === 'ar'
}

function readStoredLanguage(): Language {
  if (typeof window === 'undefined') return 'en'
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return isLanguage(stored) ? stored : 'en'
  } catch {
    // Private browsing / storage disabled -- English is a safe default.
    return 'en'
  }
}

function translate(language: Language, key: TranslationKey): string {
  return TRANSLATIONS[language][key] ?? TRANSLATIONS.en[key]
}

// English/LTR default -- used by any component that calls useLanguage()
// with no wrapping <LanguageProvider> above it. This is what keeps every
// pre-existing storefront test passing unchanged: without a provider,
// t() simply returns the same real English strings that used to be
// hardcoded, language is 'en', and direction is 'ltr'.
const DEFAULT_CONTEXT_VALUE: LanguageContextValue = {
  language: 'en',
  direction: 'ltr',
  setLanguage: () => {},
  toggleLanguage: () => {},
  t: (key) => translate('en', key),
}

const LanguageContext = createContext<LanguageContextValue>(DEFAULT_CONTEXT_VALUE)

interface LanguageProviderProps {
  children: ReactNode
}

/** The single source of truth for the customer storefront's selected
 * language (English default, Arabic optional) -- persisted to
 * localStorage so a refresh or reopened tab keeps the user's choice. Wrap
 * ONLY the parts of the app that should ever render Arabic/RTL; the admin
 * tools (AdminLayout and everything under it) never call useLanguage()
 * and so are entirely unaffected regardless of where this provider sits
 * in the tree -- see App.tsx for exactly where it's mounted. */
export function LanguageProvider({ children }: LanguageProviderProps) {
  const [language, setLanguageState] = useState<Language>(() => readStoredLanguage())

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, language)
    } catch {
      // Best-effort only -- a private-browsing/storage-disabled session
      // simply won't persist the choice across reloads.
    }
  }, [language])

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(next)
  }, [])

  const toggleLanguage = useCallback(() => {
    setLanguageState((prev) => (prev === 'en' ? 'ar' : 'en'))
  }, [])

  const t = useCallback<TranslateFn>((key) => translate(language, key), [language])

  const value = useMemo<LanguageContextValue>(
    () => ({
      language,
      direction: DIRECTION_BY_LANGUAGE[language],
      setLanguage,
      toggleLanguage,
      t,
    }),
    [language, setLanguage, toggleLanguage, t],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage(): LanguageContextValue {
  return useContext(LanguageContext)
}
