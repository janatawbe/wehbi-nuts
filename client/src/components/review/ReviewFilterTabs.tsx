import type { DigitizedProduct } from '../../types/digitizer'

export type ReviewFilter = 'needs_review' | 'duplicates' | 'approved' | 'rejected'

const TABS: { key: ReviewFilter; label: string }[] = [
  { key: 'needs_review', label: 'Review' },
  { key: 'duplicates', label: 'Duplicates' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
]

/** THE single frontend definition of "does this product currently need a
 * duplicate-resolution decision" -- every badge, warning banner, filter,
 * and count in the review UI must go through this function rather than
 * re-deriving its own version, so they can never disagree with each
 * other. Reads the backend-computed `has_unresolved_duplicates` (itself
 * derived from per-relationship match resolution, not the historical
 * existence of a match -- see DigitizedProduct.has_unresolved_duplicates)
 * and additionally excludes a merged-away record: it is a terminal,
 * locked state and must never be presented as still actionable, even if
 * one of its relationships technically remains unresolved from its side. */
export function isUnresolvedDuplicate(product: DigitizedProduct): boolean {
  return product.review_status !== 'merged' && product.has_unresolved_duplicates
}

/** Only four workflow states are shown at all: Review, Duplicates,
 * Approved, Rejected. Draft is not a separate workflow -- a draft is
 * simply a review-in-progress and stays in Review. A merged-away record
 * never matches any of these (review_status is neither pending_review nor
 * draft, and isUnresolvedDuplicate excludes MERGED on principle) -- it's
 * a terminal, locked record that is only ever reached via the canonical
 * survivor's own "Duplicate history", never listed as if it still needed
 * action. A product with an unresolved duplicate is shown ONLY under
 * Duplicates while unresolved, never simultaneously under Review -- once
 * resolved, it reappears in Review (if still awaiting approval). */
export function matchesFilter(product: DigitizedProduct, filter: ReviewFilter): boolean {
  const isDraftOrPending = product.review_status === 'pending_review' || product.review_status === 'draft'
  switch (filter) {
    case 'needs_review':
      return isDraftOrPending && !isUnresolvedDuplicate(product)
    case 'duplicates':
      return isUnresolvedDuplicate(product)
    case 'approved':
      return product.review_status === 'approved'
    case 'rejected':
      return product.review_status === 'rejected'
  }
}

interface ReviewFilterTabsProps {
  active: ReviewFilter
  onChange: (filter: ReviewFilter) => void
}

export function ReviewFilterTabs({ active, onChange }: ReviewFilterTabsProps) {
  return (
    <div className="flex flex-wrap items-center gap-1" role="tablist">
      {TABS.map((tab) => {
        const isActive = tab.key === active
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.key)}
            className={`rounded-md px-2.5 py-1 text-sm font-medium ${
              isActive ? 'bg-roast-700 text-white' : 'text-stone-600 hover:bg-stone-100'
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
