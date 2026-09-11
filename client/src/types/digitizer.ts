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

export interface FieldReviewEntry {
  needs_review: boolean
  reason: string | null
}

export type FieldReview = Record<string, FieldReviewEntry>

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
}
