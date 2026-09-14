import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'md' | 'sm'

const VARIANT_CLASSES: Record<Variant, string> = {
  // Primary: the one recommended next action (Upload, Process, Approve...).
  // Restrained roastery green, not a generic SaaS blue/emerald.
  primary:
    'bg-accent-600 text-white shadow-sm hover:bg-accent-700 focus-visible:outline-accent-700 disabled:hover:bg-accent-600',
  // Secondary: supporting actions (Save, Save as Draft, navigation).
  secondary:
    'border border-stone-300 bg-white text-stone-700 hover:bg-stone-50 focus-visible:outline-roast-600 disabled:hover:bg-white',
  // Ghost: low-emphasis actions inside cards/toolbars.
  ghost: 'text-roast-700 hover:bg-roast-50 focus-visible:outline-roast-600 disabled:hover:bg-transparent',
  // Danger: destructive actions (Reject) -- same solid, filled prominence
  // as primary, just red instead of green, so it never reads as a lesser
  // "just a link" action next to Approve.
  danger:
    'bg-red-600 text-white shadow-sm hover:bg-red-700 focus-visible:outline-red-700 disabled:hover:bg-red-600',
}

const SIZE_CLASSES: Record<Size, string> = {
  md: 'px-4 py-2 text-sm',
  sm: 'px-3 py-1.5 text-xs',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  children: ReactNode
}

/** Shared button used across the Digitizer and Review UIs so primary vs.
 * secondary vs. destructive actions read consistently everywhere (see the
 * Milestone 7 UX renovation's "Approval Action Area" requirement) instead
 * of every screen inventing its own button styling. */
export function Button({ variant = 'secondary', size = 'md', className = '', type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      {...props}
    />
  )
}
