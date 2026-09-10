export type DigitizationJobStatus = 'pending' | 'processing' | 'completed' | 'failed'

export type ProductPresentation =
  | 'packaged'
  | 'jar'
  | 'bottle'
  | 'bulk_tray'
  | 'bulk_loose'
  | 'other'

export type IdentificationBasis = 'visual' | 'text' | 'visual_and_text'

export interface DigitizedProduct {
  id: string
  source_image: string | null
  crop_image: string | null
  name_en: string | null
  name_ar: string | null
  category_suggestion: string | null
  presentation: ProductPresentation | null
  ai_confidence: string | null
  identification_basis: IdentificationBasis | null
  visible_text: string | null
  notes: string | null
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
