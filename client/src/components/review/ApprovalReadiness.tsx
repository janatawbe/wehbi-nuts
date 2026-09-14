import type { DigitizedProduct, SellingMode } from '../../types/digitizer'

interface ReadinessFormLike {
  name_en: string
  name_ar: string
  category_id: string
  selling_mode: '' | SellingMode
  price: string
}

/** Informational-only mirror of the backend's approval requirements
 * (app.services.digitizer_review_service.validate_for_approval) -- never
 * blocks the Approve button and never substitutes for the real backend
 * check. Silent once nothing is missing -- the Approve button itself is
 * the only "you're ready" signal needed. */
export function computeMissingRequiredFields(form: ReadinessFormLike, product: DigitizedProduct): string[] {
  const missing: string[] = []
  if (!form.name_en.trim()) missing.push('English name')
  if (!form.name_ar.trim()) missing.push('Arabic name')
  if (!form.category_id) missing.push('Category')
  if (!form.selling_mode) missing.push('Selling mode')
  if (!form.price.trim() || Number(form.price) <= 0) missing.push('Price')
  if (!product.crop_image && !product.refined_image) missing.push('Product image')
  return missing
}

export function ApprovalReadiness({ missing }: { missing: string[] }) {
  if (missing.length === 0) return null

  return (
    <p className="text-sm text-amber-700" data-testid="approval-readiness">
      Missing: {missing.join(', ')}
    </p>
  )
}
