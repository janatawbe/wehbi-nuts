import { Link } from 'react-router-dom'
import { useLanguage } from '../../i18n/LanguageContext'
import { localizedField } from '../../i18n/translations'
import type { StorefrontCategory } from '../../types/storefront'
import { CATEGORY_IMAGES } from './categoryImages'

interface CategoryTileProps {
  category: StorefrontCategory
}

export function CategoryTile({ category }: CategoryTileProps) {
  const { language } = useLanguage()
  const image = CATEGORY_IMAGES[category.slug]
  const name = localizedField(category.name_en, category.name_ar, language)

  return (
    <Link
      to={`/category/${category.slug}`}
      className="group flex flex-col items-center gap-3 text-center focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-wehbi-red-600 rounded-full"
    >
      <span className="relative h-20 w-20 shrink-0 rounded-full bg-cream shadow-[0_10px_24px_-8px_rgba(44,28,17,0.28)] ring-1 ring-roast-900/5 transition-all duration-300 ease-out group-hover:-translate-y-1 group-hover:shadow-[0_18px_30px_-10px_rgba(195,28,37,0.35)] sm:h-28 sm:w-28 lg:h-32 lg:w-32">
        {image && (
          <img
            src={image}
            alt=""
            className="h-full w-full rounded-full object-cover transition-transform duration-300 ease-out group-hover:scale-[1.06]"
          />
        )}
      </span>
      <span className="font-body text-sm font-medium text-roast-900 sm:text-base">{name}</span>
    </Link>
  )
}
