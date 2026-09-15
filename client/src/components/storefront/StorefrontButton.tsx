import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router-dom'

type Variant = 'primary' | 'secondary' | 'ghost'

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: 'bg-wehbi-red-600 text-white shadow-sm hover:bg-wehbi-red-700',
  secondary: 'border border-roast-900/15 bg-white text-roast-900 hover:bg-cream-deep',
  ghost: 'text-roast-900 hover:bg-roast-900/5',
}

const SHARED = 'inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wehbi-red-600 disabled:cursor-not-allowed disabled:opacity-50'

interface StorefrontButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  children: ReactNode
}

/** The storefront's own primary/secondary button -- deliberately separate
 * from components/ui/Button (the admin tools' green-primary system): the
 * customer-facing brand is red/gold, not the admin roastery-green, and
 * the two must never bleed into each other. */
export function StorefrontButton({ variant = 'primary', className = '', type = 'button', ...props }: StorefrontButtonProps) {
  return <button type={type} className={`${SHARED} ${VARIANT_CLASSES[variant]} ${className}`} {...props} />
}

interface StorefrontLinkButtonProps {
  to: string
  variant?: Variant
  children: ReactNode
  className?: string
}

/** Same visual language as StorefrontButton, for when the action is
 * really a navigation (e.g. the hero's "Shop" call to action). */
export function StorefrontLinkButton({ to, variant = 'primary', children, className = '' }: StorefrontLinkButtonProps) {
  return (
    <Link to={to} className={`${SHARED} ${VARIANT_CLASSES[variant]} ${className}`}>
      {children}
    </Link>
  )
}
