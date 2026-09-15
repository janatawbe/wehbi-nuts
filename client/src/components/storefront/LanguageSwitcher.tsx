import { useLanguage } from '../../i18n/LanguageContext'
import type { Language } from '../../i18n/translations'

const OPTIONS: { code: Language; label: string }[] = [
  { code: 'en', label: 'EN' },
  { code: 'ar', label: 'AR' },
]

interface LanguageSwitcherProps {
  className?: string
}

/** A small, elegant EN | AR toggle -- deliberately two compact pill
 * buttons in a shared rounded track (not a generic <select>/dropdown), so
 * both languages and the active one are visible at a glance. Works
 * identically in the desktop header and the mobile menu; see
 * StorefrontHeader for both placements. The labels themselves ("EN"/"AR")
 * are language CODES, not translated content -- they stay the same
 * regardless of which language is currently active. */
export function LanguageSwitcher({ className = '' }: LanguageSwitcherProps) {
  const { language, setLanguage, t } = useLanguage()

  return (
    <div
      role="group"
      aria-label={t('lang.switcher.label')}
      className={`inline-flex shrink-0 items-center gap-0.5 rounded-full border border-stone-200 bg-white p-0.5 ${className}`}
    >
      {OPTIONS.map((option) => {
        const active = language === option.code
        return (
          <button
            key={option.code}
            type="button"
            aria-pressed={active}
            onClick={() => setLanguage(option.code)}
            className={`rounded-full px-2.5 py-1 text-xs font-semibold transition-colors ${
              active ? 'bg-wehbi-red-600 text-white' : 'text-roast-800 hover:text-wehbi-red-700'
            }`}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
