import wehbiLogoMark from '../../assets/wehbi-logo-mark.png'
import { useLanguage } from '../../i18n/LanguageContext'

export function StorefrontFooter() {
  const { t } = useLanguage()

  return (
    <footer className="border-t border-stone-200/70 bg-cream-deep">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <img src={wehbiLogoMark} alt="Wehbi Nuts" className="h-10 w-10" />
          <p className="font-display text-lg font-semibold text-roast-900">Wehbi Nuts</p>
        </div>
        <p className="mt-8 text-center text-xs text-stone-400">
          © {new Date().getFullYear()} Wehbi Nuts. {t('footer.rights')}
        </p>
      </div>
    </footer>
  )
}
