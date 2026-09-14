import { getDigitizerMediaUrl } from '../../api/digitizer'
import type { DigitizedProduct } from '../../types/digitizer'

function refinementNote(product: DigitizedProduct): string | null {
  switch (product.image_refinement_status) {
    case 'pending':
      return 'Not prepared yet.'
    case 'skipped':
      return 'No detected-product photo was available to prepare a final image from.'
    case 'failed':
      return 'The last attempt to prepare the final image failed -- the detected product photo is shown instead.'
    case 'refined':
      return null
  }
}

interface ImageComparisonProps {
  product: DigitizedProduct
}

/** Shows only the product image that matters day-to-day -- the final
 * (refined) image, falling back to the detected crop when it isn't ready
 * yet. The original photo and detected crop stay available, just tucked
 * behind a small disclosure instead of competing for equal attention. */
export function ImageComparison({ product }: ImageComparisonProps) {
  const note = refinementNote(product)
  const mainImage = product.refined_image
    ? { src: getDigitizerMediaUrl(product.job_id, 'refined', product.refined_image), kind: 'refined' as const }
    : product.crop_image
      ? { src: getDigitizerMediaUrl(product.job_id, 'products', product.crop_image), kind: 'crop' as const }
      : null

  return (
    <div>
      <p className="text-sm font-medium text-stone-700">
        Product image
        <span className="text-red-600" aria-hidden="true">
          {' '}
          *
        </span>
      </p>

      <div className="mt-1.5 aspect-square w-full max-w-xs overflow-hidden rounded-md bg-stone-100">
        {mainImage ? (
          <img
            src={mainImage.src}
            alt={product.name_en ?? 'Product'}
            className="h-full w-full object-contain"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-stone-400">No image</div>
        )}
      </div>
      {note && (
        <p className="mt-1 text-xs text-stone-400" data-testid="refinement-note">
          {note}
        </p>
      )}

      {(product.source_image || product.crop_image) && (
        <details className="mt-1.5">
          <summary className="cursor-pointer text-xs text-stone-400 hover:text-stone-600">
            View original images
          </summary>
          <div className="mt-2 flex gap-3">
            {product.source_image && (
              <div>
                <p className="mb-1 text-[11px] text-stone-400">Original photo</p>
                <img
                  src={getDigitizerMediaUrl(product.job_id, 'source', product.source_image)}
                  alt="Original uploaded photo"
                  className="h-24 w-24 rounded border border-stone-200 object-contain bg-stone-50"
                />
              </div>
            )}
            {product.crop_image && (
              <div>
                <p className="mb-1 text-[11px] text-stone-400">Detected product</p>
                <img
                  src={getDigitizerMediaUrl(product.job_id, 'products', product.crop_image)}
                  alt="Detected product"
                  className="h-24 w-24 rounded border border-stone-200 object-contain bg-stone-50"
                />
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  )
}
