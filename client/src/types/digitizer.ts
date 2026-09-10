export type DigitizationJobStatus = 'pending' | 'processing' | 'completed' | 'failed'

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
}
