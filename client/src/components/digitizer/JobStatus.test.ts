import { describe, expect, it } from 'vitest'
import type { DigitizedProduct, DigitizerJob } from '../../types/digitizer'
import { computeJobStatus } from './JobStatus'

const BASE_CANDIDATE: DigitizedProduct = {
  id: 'p1',
  job_id: 'job-1',
  source_image: 's.jpg',
  crop_image: 'c.jpg',
  name_en: 'Almonds',
  name_ar: null,
  category_suggestion: null,
  category_id: null,
  presentation: null,
  ai_confidence: null,
  identification_basis: null,
  visible_text: null,
  notes: null,
  brand: null,
  flavor_variant: null,
  description_en: null,
  description_ar: null,
  selling_mode: null,
  package_weight: null,
  barcode: null,
  field_review: null,
  enrichment_status: 'pending',
  refined_image: null,
  image_refinement_status: 'pending',
  background_isolation_status: 'not_attempted',
  duplicate_status: 'not_checked',
  duplicate_group_id: null,
  duplicate_matches: [],
  price: null,
  stock_status: 'in_stock',
  review_status: 'pending_review',
  duplicate_resolution: 'unresolved',
  reviewed_at: null,
  approved_at: null,
  merged_into_id: null,
  product_id: null,
  has_unresolved_duplicates: false,
}

function makeJob(overrides: Partial<DigitizerJob> = {}): DigitizerJob {
  return {
    id: 'job-1',
    status: 'pending',
    total_items: 1,
    processed_items: 0,
    failed_items: 0,
    error_message: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    source_images: ['s.jpg'],
    candidates: [],
    duplicate_summary: null,
    ...overrides,
  }
}

describe('computeJobStatus', () => {
  it('a freshly uploaded job recommends processing next', () => {
    const { message, nextAction } = computeJobStatus(makeJob({ status: 'pending', total_items: 3 }))

    expect(message).toContain('3 photos')
    expect(nextAction).toEqual({ key: 'process', label: 'Process Photos' })
  })

  it('a failed job needs attention and offers a retry', () => {
    const { message, nextAction } = computeJobStatus(makeJob({ status: 'failed' }))

    expect(message).toBe('Needs attention')
    expect(nextAction).toEqual({ key: 'process', label: 'Retry Processing' })
  })

  it('after detection, recommends preparing products next', () => {
    const { nextAction } = computeJobStatus(makeJob({ status: 'completed', candidates: [BASE_CANDIDATE] }))

    expect(nextAction).toEqual({ key: 'enrich', label: 'Prepare Products' })
  })

  it('once prepared, recommends preparing images', () => {
    const job = makeJob({
      status: 'completed',
      candidates: [{ ...BASE_CANDIDATE, enrichment_status: 'enriched' }],
    })
    expect(computeJobStatus(job).nextAction).toEqual({ key: 'refine', label: 'Prepare Images' })
  })

  it('once images are ready, recommends checking for duplicates', () => {
    const job = makeJob({
      status: 'completed',
      candidates: [
        { ...BASE_CANDIDATE, enrichment_status: 'enriched', image_refinement_status: 'refined' },
      ],
      duplicate_summary: {
        total_candidates: 1,
        eligible_candidates: 1,
        skipped_not_enriched: 0,
        likely_count: 0,
        possible_count: 0,
        none_count: 0,
      },
    })
    expect(computeJobStatus(job).nextAction).toEqual({ key: 'detect_duplicates', label: 'Check for Duplicates' })
  })

  it('once every stage has run, there is no next action -- just a ready message', () => {
    const job = makeJob({
      status: 'completed',
      candidates: [
        {
          ...BASE_CANDIDATE,
          enrichment_status: 'enriched',
          image_refinement_status: 'refined',
          duplicate_status: 'none',
        },
      ],
      duplicate_summary: {
        total_candidates: 1,
        eligible_candidates: 1,
        skipped_not_enriched: 0,
        likely_count: 0,
        possible_count: 0,
        none_count: 1,
      },
    })
    const { message, nextAction } = computeJobStatus(job)
    expect(nextAction).toBeNull()
    expect(message).toContain('ready for review')
  })

  it('a job actively processing shows no action -- nothing to click while it runs', () => {
    expect(computeJobStatus(makeJob({ status: 'processing' })).nextAction).toBeNull()
  })
})
