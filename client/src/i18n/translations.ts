/** Milestone 9 storefront i18n: every FIXED piece of customer-facing UI
 * copy lives here, centrally, keyed by a stable dot-path string -- never
 * scattered as `language === 'ar' ? '...' : '...'` conditionals through
 * individual components. See LanguageContext.tsx for the provider/hook
 * that reads this dictionary.
 *
 * Deliberately customer-storefront-only: the admin tools (AdminLayout and
 * everything under it) never import from this module and stay English,
 * regardless of the storefront's selected language.
 *
 * Product/category NAMES are NOT here -- those are real bilingual
 * database fields (Product.name_en/name_ar, Category.name_en/name_ar),
 * selected via `localizedField` below, never hardcoded translations.
 */

export type Language = 'en' | 'ar'
export type Direction = 'ltr' | 'rtl'

const en = {
  'nav.home': 'Home',
  'nav.shop': 'Shop',
  'nav.cart': 'Cart',
  'nav.menu': 'Menu',
  'nav.backHome': 'Back to Home',
  'nav.search.label': 'Search products',
  'nav.search.placeholder': 'Search nuts, coffee, sweets...',

  'lang.switcher.label': 'Language',

  'hero.eyebrow': 'Nuts · Coffee · Sweets · Dried Fruit · Spices · Gifts',
  'hero.title.line1': 'Freshly roasted,',
  'hero.title.line2': 'endlessly snackable',
  'hero.subtitle': 'From crunchy nuts to rich coffee and sweet treats, find something for every craving.',
  'hero.cta': 'Shop Now',

  'category.heading': 'Shop by Category',
  'category.subheading': 'Find your favorites, all in one place.',

  'featured.heading': 'Featured Picks',
  'featured.subheading': "A small taste of what's in store.",
  'featured.viewAll': 'Shop all',

  'gifting.heading': 'Treat yourself, or someone good.',
  'gifting.body': 'A thoughtful little gesture can turn an ordinary moment into something worth remembering.',

  'shop.title': 'Shop',
  'shop.filter.all': 'All',
  'shop.filter.label': 'Filter by category',
  'shop.search.label': 'Search products',
  'shop.search.placeholder': 'Search products...',
  'shop.empty': 'No products match your search yet.',
  'products.empty': 'No products found.',

  'category.notFound.title': 'Category not found',
  'category.notFound.body': "We couldn't find that category.",
  'category.browseShop': 'Browse the full shop',
  'category.empty': 'No products in this category yet.',

  'product.soldOut': 'Sold out',
  'product.stock.low': 'Low stock',
  'product.stock.out': 'Out of stock',
  'product.pricePerKg': 'priced per kilogram',
  'product.package': 'package',
  'product.category': 'Category',
  'product.brand': 'Brand',
  'product.notFound.title': 'Product not found',
  'product.notFound.body': "This product isn't available.",
  'product.loadError': 'Could not load this product.',
  'product.breadcrumb.shop': 'Shop',

  'products.loadError': 'Could not load products.',

  'unit.g': 'g',
  'unit.kg': 'kg',

  'cart.empty.title': 'Your cart is empty',
  'cart.empty.body': "Online ordering is coming soon -- for now, browse the shop to see what's available.",
  'cart.continueShopping': 'Continue Shopping',

  'notFound.title': 'Page not found',
  'notFound.body': "The page you're looking for doesn't exist.",
  'notFound.browseShop': 'Or browse the shop',

  'footer.rights': 'All rights reserved.',
} as const

const ar: Record<keyof typeof en, string> = {
  'nav.home': 'الرئيسية',
  'nav.shop': 'المتجر',
  'nav.cart': 'السلة',
  'nav.menu': 'القائمة',
  'nav.backHome': 'العودة إلى الرئيسية',
  'nav.search.label': 'ابحث عن المنتجات',
  'nav.search.placeholder':
    'ابحث عن المكسرات، القهوة، الحلويات...',

  'lang.switcher.label': 'اللغة',

  'hero.eyebrow':
    'مكسرات · قهوة · حلويات · فواكه مجففة · بهارات · هدايا',
  'hero.title.line1': 'محمّص طازجاً،',
  'hero.title.line2': 'ولا يُقاوَم',
  'hero.subtitle':
    'من المكسرات المقرمشة إلى القهوة الغنية والحلويات الشهية، هناك ما يلبّي كل رغبة.',
  'hero.cta': 'تسوّق الآن',

  'category.heading': 'تسوّق حسب الفئة',
  'category.subheading': 'اكتشف مفضّلاتك، كلّها في مكان واحد.',

  'featured.heading': 'منتجات مختارة',
  'featured.subheading': 'لمحة بسيطة عمّا يتوفر لدينا.',
  'featured.viewAll': 'تسوّق الكل',

  'gifting.heading': 'دلّل نفسك، أو دلّل أحداً تحب.',
  'gifting.body':
    'لفتة صغيرة ومدروسة قد تحوّل لحظة عادية إلى ذكرى تستحق أن تُروى.',

  'shop.title': 'المتجر',
  'shop.filter.all': 'الكل',
  'shop.filter.label': 'تصفية حسب الفئة',
  'shop.search.label': 'ابحث عن المنتجات',
  'shop.search.placeholder': 'ابحث عن المنتجات...',
  'shop.empty': 'لا توجد منتجات مطابقة لبحثك بعد.',
  'products.empty': 'لا توجد منتجات.',

  'category.notFound.title': 'الفئة غير موجودة',
  'category.notFound.body': 'لم نتمكن من العثور على هذه الفئة.',
  'category.browseShop': 'تصفّح المتجر بالكامل',
  'category.empty': 'لا توجد منتجات في هذه الفئة بعد.',

  'product.soldOut': 'نفدت الكمية',
  'product.stock.low': 'كمية محدودة',
  'product.stock.out': 'نفدت الكمية',
  'product.pricePerKg': 'السعر لكل كيلوغرام',
  'product.package': 'العبوة',
  'product.category': 'الفئة',
  'product.brand': 'العلامة التجارية',
  'product.notFound.title': 'المنتج غير موجود',
  'product.notFound.body': 'هذا المنتج غير متوفر حالياً.',
  'product.loadError': 'تعذّر تحميل هذا المنتج.',
  'product.breadcrumb.shop': 'المتجر',

  'products.loadError': 'تعذّر تحميل المنتجات.',

  'unit.g': 'غ',
  'unit.kg': 'كغ',

  'cart.empty.title': 'سلتك فارغة',
  'cart.empty.body':
    'التسوق عبر الإنترنت قادم قريباً -- تصفّح المتجر في الوقت الحالي لترى ما هو متوفر.',
  'cart.continueShopping': 'متابعة التسوق',

  'notFound.title': 'الصفحة غير موجودة',
  'notFound.body': 'الصفحة التي تبحث عنها غير موجودة.',
  'notFound.browseShop': 'أو تصفّح المتجر',

  'footer.rights': 'جميع الحقوق محفوظة.',
}

export const TRANSLATIONS: Record<Language, Record<TranslationKey, string>> = { en, ar }

export type TranslationKey = keyof typeof en
export type TranslateFn = (key: TranslationKey) => string

export const DIRECTION_BY_LANGUAGE: Record<Language, Direction> = {
  en: 'ltr',
  ar: 'rtl',
}

/** A forward-pointing arrow glyph, oriented for the given direction --
 * used anywhere a translated string is followed by a decorative "->"-style
 * arrow (e.g. "Shop all ->"), so the glyph itself flips for RTL rather
 * than always pointing visually right regardless of reading direction. */
export function forwardArrow(dir: Direction): string {
  return dir === 'rtl' ? '←' : '→'
}

/** Picks the correct localized value for a real bilingual database field
 * (Product.name_en/name_ar, Category.name_en/name_ar, etc.) -- NEVER a
 * hardcoded translation. In Arabic, prefers the Arabic field; falls back
 * to the English field when the Arabic one is empty/whitespace-only
 * (covers legacy/incomplete data without ever showing blank text). In
 * English, always uses the English field. The generic parameter mirrors
 * `en`'s own nullability, so a guaranteed-non-null field (a name) stays
 * non-null, while an optional field (a description) stays nullable. */
export function localizedField<T extends string | null>(en: T, ar: string | null | undefined, language: Language): T {
  if (language === 'ar' && ar && ar.trim()) {
    return ar as T
  }
  return en
}
