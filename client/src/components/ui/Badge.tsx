import type { ReactNode } from 'react'
import type { ReviewStatus } from '../../types/digitizer'

const REVIEW_STATUS_STYLES: Record<ReviewStatus, string> = {
  pending_review: 'bg-amber-100 text-amber-800',
  draft: 'bg-stone-200 text-stone-700',
  approved: 'bg-accent-100 text-accent-800',
  rejected: 'bg-red-100 text-red-800',
  merged: 'bg-violet-100 text-violet-800',
}

const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  pending_review: 'Needs Review',
  draft: 'Draft',
  approved: 'Approved',
  rejected: 'Rejected',
  merged: 'Merged',
}

export function ReviewStatusBadge({ status }: { status: ReviewStatus }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${REVIEW_STATUS_STYLES[status]}`}
    >
      {REVIEW_STATUS_LABELS[status]}
    </span>
  )
}

export type BadgeTone = 'neutral' | 'warning' | 'danger' | 'info' | 'success' | 'brand'

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: 'bg-stone-100 text-stone-600',
  warning: 'bg-amber-100 text-amber-800',
  danger: 'bg-red-100 text-red-700',
  info: 'bg-stone-200 text-stone-700',
  success: 'bg-accent-100 text-accent-800',
  brand: 'bg-roast-100 text-roast-800',
}

/** Small pill used everywhere a concise status word is needed (product
 * cards, review rows, workflow steps) -- one shared visual language for
 * "what state is this in" instead of every screen styling its own. Keep
 * the number of badges shown on any one item small (progressive
 * disclosure) -- see ProductCandidateCard/ReviewProductList. */
export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: BadgeTone }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}>
      {children}
    </span>
  )
}
