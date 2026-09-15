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
  'shop.subheading': 'Everything roasted, packed, and ready for you.',
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
  'product.description.label': 'Description',
  'product.notFound.title': 'Product not found',
  'product.notFound.body': "This product isn't available.",
  'product.loadError': 'Could not load this product.',
  'product.breadcrumb.shop': 'Shop',

  'products.loadError': 'Could not load products.',

  'unit.g': 'g',
  'unit.kg': 'kg',

  'cart.title': 'Your Cart',
  'cart.section.items': 'Your Items',
  'cart.empty.title': 'Your cart is empty',
  'cart.empty.body': "You haven't added anything yet. Browse the shop to find something you'll love.",
  'cart.continueShopping': 'Continue Shopping',
  'cart.item.remove': 'Remove',
  'cart.item.decrease': 'Decrease',
  'cart.item.increase': 'Increase',
  'cart.orderTotal': 'Order Total',
  'cart.checkout': 'Checkout',

  'product.addToCart': 'Add to Cart',
  'product.added': 'Added',
  'product.addedToCart': 'Added to cart',
  'product.weight.label': 'Weight',
  'product.weight.unit.label': 'Weight unit',
  'product.weight.invalid': 'Enter a weight greater than 0.',
  'product.weight.priceForAmount': 'Price for this amount',
  'product.quantity.label': 'Quantity',

  'checkout.title': 'Checkout',
  'checkout.section.delivery': 'Delivery Details',
  'checkout.field.name': 'Full Name',
  'checkout.field.phone': 'Phone Number',
  'checkout.field.address': 'Delivery Address',
  'checkout.field.area': 'Area / Neighborhood',
  'checkout.field.notes': 'Delivery Note (optional)',
  'checkout.validation.required': 'This field is required.',
  'checkout.payment.label': 'Payment Method',
  'checkout.payment.cod': 'Cash on Delivery',
  'checkout.payment.codDescription': 'Pay in cash when your order arrives at your door.',
  'checkout.placeOrder': 'Place Order',
  'checkout.submitting': 'Placing your order...',
  'checkout.error.generic': 'Something went wrong placing your order. Please try again.',
  'checkout.emptyCart.body': 'Your cart is empty. Add something from the shop before checking out.',

  'order.summary.title': 'Order Summary',

  'orderSuccess.title': 'Order Confirmed!',
  'orderSuccess.thankYou': 'Thank you for your order.',
  'orderSuccess.orderNumber': 'Order Number',
  'orderSuccess.codNotice': "You'll pay in cash when your order is delivered.",
  'orderSuccess.invalid.title': 'No order to show',
  'orderSuccess.invalid.body': "It looks like you got here directly. Please return to the shop to place an order.",

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
  'shop.subheading': 'كل شيء محمّص ومعبأ وجاهز لك.',
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
  'product.description.label': 'الوصف',
  'product.notFound.title': 'المنتج غير موجود',
  'product.notFound.body': 'هذا المنتج غير متوفر حالياً.',
  'product.loadError': 'تعذّر تحميل هذا المنتج.',
  'product.breadcrumb.shop': 'المتجر',

  'products.loadError': 'تعذّر تحميل المنتجات.',

  'unit.g': 'غ',
  'unit.kg': 'كغ',

  'cart.title': 'سلة التسوق',
  'cart.section.items': 'عناصر السلة',
  'cart.empty.title': 'سلتك فارغة',
  'cart.empty.body': 'لم تضِف أي شيء بعد. تصفّح المتجر لتجد ما يعجبك.',
  'cart.continueShopping': 'متابعة التسوق',
  'cart.item.remove': 'إزالة',
  'cart.item.decrease': 'إنقاص',
  'cart.item.increase': 'زيادة',
  'cart.orderTotal': 'إجمالي الطلب',
  'cart.checkout': 'إتمام الطلب',

  'product.addToCart': 'أضف إلى السلة',
  'product.added': 'أُضيف',
  'product.addedToCart': 'تمت الإضافة إلى السلة',
  'product.weight.label': 'الوزن',
  'product.weight.unit.label': 'وحدة الوزن',
  'product.weight.invalid': 'أدخل وزناً أكبر من الصفر.',
  'product.weight.priceForAmount': 'السعر لهذه الكمية',
  'product.quantity.label': 'الكمية',

  'checkout.title': 'إتمام الطلب',
  'checkout.section.delivery': 'تفاصيل التوصيل',
  'checkout.field.name': 'الاسم الكامل',
  'checkout.field.phone': 'رقم الهاتف',
  'checkout.field.address': 'عنوان التوصيل',
  'checkout.field.area': 'المنطقة / الحي',
  'checkout.field.notes': 'ملاحظة التوصيل (اختياري)',
  'checkout.validation.required': 'هذا الحقل مطلوب.',
  'checkout.payment.label': 'طريقة الدفع',
  'checkout.payment.cod': 'الدفع عند الاستلام',
  'checkout.payment.codDescription': 'ادفع نقداً عند وصول طلبك إلى بابك.',
  'checkout.placeOrder': 'تأكيد الطلب',
  'checkout.submitting': 'جارٍ تنفيذ الطلب...',
  'checkout.error.generic': 'حدث خطأ أثناء تنفيذ الطلب. حاول مرة أخرى.',
  'checkout.emptyCart.body': 'سلتك فارغة. أضف شيئاً من المتجر قبل إتمام الطلب.',

  'order.summary.title': 'ملخص الطلب',

  'orderSuccess.title': 'تم تأكيد طلبك!',
  'orderSuccess.thankYou': 'شكراً لطلبك.',
  'orderSuccess.orderNumber': 'رقم الطلب',
  'orderSuccess.codNotice': 'سيتم الدفع نقداً عند استلام الطلب.',
  'orderSuccess.invalid.title': 'لا يوجد طلب لعرضه',
  'orderSuccess.invalid.body': 'يبدو أنك وصلت إلى هنا مباشرة. الرجاء العودة إلى المتجر لإتمام عملية شراء.',

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
