export type DigitizationJobStatus = 'pending' | 'processing' | 'completed' | 'failed'

export type ProductPresentation =
  | 'packaged'
  | 'jar'
  | 'bottle'
  | 'bulk_tray'
  | 'bulk_loose'
  | 'other'

export type IdentificationBasis = 'visual' | 'text' | 'visual_and_text'

// Milestone 5 enrichment. `selling_mode` is how a product is SOLD, and is
// independent of `package_weight` (a printed label weight) -- a packaged
// 500g bag is still selling_mode="unit" with package_weight="0.500".
export type SellingMode = 'weight' | 'unit'

export type EnrichmentStatus = 'pending' | 'enriched'

// Milestone 6 image refinement -- see ImageRefinementStatus's backend
// docstring. "refined" is high-quality resizing/composition (Pillow), plus
// attempted background isolation for every suitable presentation
// (including bulk/loose) -- never true AI super-resolution/generative
// upscaling, and never generative recreation of product content.
export type ImageRefinementStatus = 'pending' | 'refined' | 'failed' | 'skipped'

// Whether Tier 2 background isolation was attempted and its outcome --
// distinct from image_refinement_status (the overall pipeline still
// succeeds via Tier-1-only fallback even when isolation is rejected).
export type BackgroundIsolationStatus = 'not_attempted' | 'applied' | 'rejected'

// Milestone 6 duplicate detection -- flags only, scoped to one job, never
// merges/deletes. See DuplicateStatus's backend docstring.
export type DuplicateStatus = 'not_checked' | 'none' | 'possible' | 'likely'

export interface FieldReviewEntry {
  needs_review: boolean
  reason: string | null
}

export type FieldReview = Record<string, FieldReviewEntry>

export interface DuplicateMatch {
  matched_product_id: string
  matched_name_en: string | null
  score: string
  reasons: string[]
}

export interface DigitizedProduct {
  id: string
  job_id: string
  source_image: string | null
  crop_image: string | null
  name_en: string | null
  name_ar: string | null
  category_suggestion: string | null
  category_id: string | null
  presentation: ProductPresentation | null
  ai_confidence: string | null
  identification_basis: IdentificationBasis | null
  visible_text: string | null
  notes: string | null

  // Milestone 5 enrichment -- null/absent until "Enrich" has been run.
  brand: string | null
  flavor_variant: string | null
  description_en: string | null
  description_ar: string | null
  selling_mode: SellingMode | null
  package_weight: string | null
  barcode: string | null
  field_review: FieldReview | null
  enrichment_status: EnrichmentStatus

  // Milestone 6 image refinement -- null/pending until "Refine" has been run.
  refined_image: string | null
  image_refinement_status: ImageRefinementStatus
  background_isolation_status: BackgroundIsolationStatus

  // Milestone 6 duplicate detection -- flags only, never a merge/delete.
  duplicate_status: DuplicateStatus
  duplicate_group_id: string | null
  duplicate_matches: DuplicateMatch[]
}

// Explainable summary of a job's current duplicate-detection state --
// tells apart "never compared (not enriched yet)" from "compared, no
// duplicate found", which look identical without this. Computed fresh on
// every job read, not just right after Detect Duplicates.
export interface DuplicateDetectionSummary {
  total_candidates: number
  eligible_candidates: number
  skipped_not_enriched: number
  likely_count: number
  possible_count: number
  none_count: number
}

export interface DigitizerJob {
  id: string
  status: DigitizationJobStatus
  total_items: number
  processed_items: number
  failed_items: number
  error_message: string | null
  created_at: string
  updated_at: string
  source_images: string[]
  candidates: DigitizedProduct[]
  duplicate_summary: DuplicateDetectionSummary | null
}
