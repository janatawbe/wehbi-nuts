import { getDigitizerMediaUrl } from '../../api/digitizer'
import type { DigitizedProduct } from '../../types/digitizer'
import { Badge, ReviewStatusBadge } from '../ui/Badge'
import { isUnresolvedDuplicate, type ReviewFilter } from './ReviewFilterTabs'

function thumbnail(product: DigitizedProduct): string | null {
  if (product.refined_image) return getDigitizerMediaUrl(product.job_id, 'refined', product.refined_image)
  if (product.crop_image) return getDigitizerMediaUrl(product.job_id, 'products', product.crop_image)
  return null
}

interface ReviewProductListProps {
  products: DigitizedProduct[]
  filter: ReviewFilter
  selectedProductId: string | null
  onSelectProduct: (id: string) => void
}

export function ReviewProductList({
  products,
  filter,
  selectedProductId,
  onSelectProduct,
}: ReviewProductListProps) {
  if (products.length === 0) {
    return <p className="py-6 text-center text-sm text-stone-500">No products match this filter.</p>
  }

  return (
    <ul className="divide-y divide-stone-100" data-testid="review-product-list">
      {products.map((product) => {
        const isSelected = product.id === selectedProductId
        const image = thumbnail(product)
        const unresolvedDuplicate = isUnresolvedDuplicate(product)
        return (
          <li
            key={product.id}
            data-testid={`review-row-${product.id}`}
            className={`rounded-lg transition-colors ${
              isSelected ? 'bg-roast-50 ring-1 ring-inset ring-roast-300' : 'hover:bg-stone-50'
            }`}
          >
            <button
              type="button"
              onClick={() => onSelectProduct(product.id)}
              className="flex w-full min-w-0 items-center gap-3 px-2 py-2.5 text-left"
              aria-current={isSelected ? 'true' : undefined}
            >
              <div className="h-14 w-14 shrink-0 overflow-hidden rounded-md bg-stone-100">
                {image ? (
                  <img
                    src={image}
                    alt={product.name_en ?? 'Product'}
                    className="h-full w-full object-contain"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-[10px] text-stone-400">
                    No image
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-stone-900">
                  {product.name_en ?? '(no English name yet)'}
                </p>
                {product.price && <p className="truncate text-xs text-stone-500">${product.price}</p>}
                {/* Every OTHER tab is homogeneous by construction (every row
                    already shares the tab's own status), so a status badge
                    there would just repeat the tab. Duplicates is the one
                    tab that mixes different review statuses together, so
                    that's the one place a status badge adds real
                    information; everywhere else, the only thing worth a
                    badge is an unresolved duplicate the tab itself doesn't
                    already say. */}
                {filter === 'duplicates' ? (
                  <div className="mt-1">
                    <ReviewStatusBadge status={product.review_status} />
                  </div>
                ) : (
                  unresolvedDuplicate && (
                    <div className="mt-1">
                      <Badge tone="warning">Possible Duplicate</Badge>
                    </div>
                  )
                )}
              </div>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
