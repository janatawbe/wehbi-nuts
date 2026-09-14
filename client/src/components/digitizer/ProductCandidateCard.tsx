import { useState } from 'react'
import { getDigitizerMediaUrl } from '../../api/digitizer'
import type { DigitizedProduct } from '../../types/digitizer'
import { Badge, type BadgeTone } from '../ui/Badge'
import { Button } from '../ui/Button'

/** Best available image for a candidate that hasn't been reviewed yet --
 * prefers the Milestone 6 refined image, falls back to the raw crop. */
function bestImage(jobId: string, product: DigitizedProduct): string | null {
  if (product.refined_image) return getDigitizerMediaUrl(jobId, 'refined', product.refined_image)
  if (product.crop_image) return getDigitizerMediaUrl(jobId, 'products', product.crop_image)
  return null
}

/** At most one status word -- only when it's something the user would
 * plausibly act on or that meaningfully distinguishes this card from a
 * routine one. "Needs review" is deliberately never shown here: it's the
 * default state for everything on this page, so labeling it on every
 * card would just be noise. */
function status(product: DigitizedProduct): { label: string; tone: BadgeTone } | null {
  if (product.review_status === 'merged') return { label: 'Merged', tone: 'neutral' }
  if (product.review_status === 'approved') return { label: 'Approved', tone: 'success' }
  if (product.has_unresolved_duplicates) return { label: 'Possible duplicate', tone: 'warning' }
  return null
}

interface ProductCandidateCardProps {
  jobId: string
  product: DigitizedProduct
  enriching: boolean
  enrichError: string | null
  onEnrich: () => void
  refining: boolean
  refineError: string | null
  onRefine: () => void
}

/** A minimal card: image, name, category, and at most one status word.
 * The whole card opens/closes its own detail (brand/flavor/barcode and
 * the Enrich/Refine actions) -- there is no separate "Details" link, the
 * card itself is the clickable/selectable unit. */
export function ProductCandidateCard({
  jobId,
  product,
  enriching,
  enrichError,
  onEnrich,
  refining,
  refineError,
  onRefine,
}: ProductCandidateCardProps) {
  const [showDetails, setShowDetails] = useState(false)
  const image = bestImage(jobId, product)
  const productStatus = status(product)

  return (
    <li className="min-w-0" data-testid="digitized-product">
      <button
        type="button"
        onClick={() => setShowDetails((prev) => !prev)}
        aria-expanded={showDetails}
        data-testid="toggle-product-details"
        className="block w-full rounded-md text-left transition-shadow hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-roast-600"
      >
        <div className="aspect-square w-full overflow-hidden rounded-md bg-stone-100">
          {image ? (
            <img
              src={image}
              alt={product.name_en ?? 'Detected product'}
              className="h-full w-full object-contain"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-xs text-stone-400">No image yet</div>
          )}
        </div>

        <p className="mt-2 truncate font-medium text-stone-900">{product.name_en ?? 'Unnamed product'}</p>
        {productStatus && (
          <div className="mt-1">
            <Badge tone={productStatus.tone}>{productStatus.label}</Badge>
          </div>
        )}
      </button>

      {showDetails && (
        <div className="mt-2 space-y-2 border-t border-stone-100 pt-2 text-xs text-stone-600">
          {(product.brand || product.flavor_variant || product.package_weight || product.barcode) && (
            <dl className="space-y-1">
              {product.brand && (
                <div>
                  <dt className="inline font-medium">Brand: </dt>
                  <dd className="inline">{product.brand}</dd>
                </div>
              )}
              {product.flavor_variant && (
                <div>
                  <dt className="inline font-medium">Flavor / variant: </dt>
                  <dd className="inline">{product.flavor_variant}</dd>
                </div>
              )}
              {product.package_weight && (
                <div>
                  <dt className="inline font-medium">Package weight: </dt>
                  <dd className="inline">{product.package_weight} kg</dd>
                </div>
              )}
              {product.barcode && (
                <div>
                  <dt className="inline font-medium">Barcode: </dt>
                  <dd className="inline">{product.barcode}</dd>
                </div>
              )}
            </dl>
          )}

          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={onEnrich} disabled={enriching} data-testid="enrich-product-button">
              {enriching ? 'Working...' : product.enrichment_status === 'enriched' ? 'Re-enrich' : 'Enrich'}
            </Button>
            <Button variant="secondary" size="sm" onClick={onRefine} disabled={refining} data-testid="refine-product-button">
              {refining ? 'Working...' : product.image_refinement_status === 'refined' ? 'Re-refine' : 'Refine'}
            </Button>
          </div>
          {enrichError && (
            <p className="text-red-600" data-testid="enrich-product-error">
              {enrichError}
            </p>
          )}
          {refineError && (
            <p className="text-red-600" data-testid="refine-product-error">
              {refineError}
            </p>
          )}
        </div>
      )}
    </li>
  )
}
