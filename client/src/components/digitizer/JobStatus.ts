import type { DigitizerJob } from '../../types/digitizer'

export type NextAction =
  | { key: 'process'; label: string }
  | { key: 'enrich'; label: string }
  | { key: 'refine'; label: string }
  | { key: 'detect_duplicates'; label: string }
  | null

const TERMINAL_REVIEW_STATUSES = new Set(['approved', 'rejected', 'merged'])

/** One plain-language status line plus (at most) one recommended next
 * action -- deliberately NOT a multi-step pipeline display. The user
 * clicks through detection/enrichment/refinement/duplicate-check one
 * action at a time without ever needing to know those are four separate
 * systems; each still costs at most one AI call per click, unchanged from
 * before -- this only simplifies the presentation. */
export function computeJobStatus(job: DigitizerJob): { message: string; nextAction: NextAction } {
  const total = job.candidates.length

  if (job.status === 'failed') {
    return { message: 'Needs attention', nextAction: { key: 'process', label: 'Retry Processing' } }
  }
  if (job.status === 'processing') {
    return { message: 'Preparing products...', nextAction: null }
  }
  if (job.status === 'pending') {
    return {
      message: `Ready to process ${job.total_items} photo${job.total_items === 1 ? '' : 's'}`,
      nextAction: { key: 'process', label: 'Process Photos' },
    }
  }
  // completed
  if (total === 0) {
    return { message: 'No products found', nextAction: null }
  }

  const enrichedCount = job.candidates.filter((c) => c.enrichment_status === 'enriched').length
  if (enrichedCount < total) {
    return { message: `${total} products found`, nextAction: { key: 'enrich', label: 'Prepare Products' } }
  }

  const imagesReady = job.candidates.filter((c) => c.image_refinement_status !== 'pending').length
  if (imagesReady < total) {
    return { message: `${total} products found`, nextAction: { key: 'refine', label: 'Prepare Images' } }
  }

  const eligible = job.duplicate_summary?.eligible_candidates ?? 0
  const checked = job.candidates.filter((c) => c.duplicate_status !== 'not_checked').length
  if (eligible > 0 && checked < eligible) {
    return { message: `${total} products found`, nextAction: { key: 'detect_duplicates', label: 'Check for Duplicates' } }
  }

  const needsReview = job.candidates.filter((c) => !TERMINAL_REVIEW_STATUSES.has(c.review_status)).length
  if (needsReview > 0) {
    return { message: `${total} products ready for review`, nextAction: null }
  }
  return { message: `${total} products reviewed`, nextAction: null }
}
