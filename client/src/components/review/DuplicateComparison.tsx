import { getDigitizerMediaUrl } from '../../api/digitizer'
import type { DigitizedProduct, DuplicateMatch } from '../../types/digitizer'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

const RESOLUTION_LABEL: Record<DuplicateMatch['resolution'], string> = {
  unresolved: 'Unresolved',
  kept_separate: 'Kept separate',
  merged: 'Merged',
}

const REASON_LABELS: Record<string, string> = {
  barcode_match: 'Matching barcode',
  brand_match: 'Matching brand',
  category_match: 'Same category',
  flavor_match: 'Same flavor / variant',
  package_weight_match: 'Same package weight',
}

/** Turns a raw evidence tag (e.g. "name_similarity:0.88") into a short,
 * human-readable phrase -- purely a display transform, never changes what
 * counts as evidence (that stays entirely backend-owned). */
function humanizeReason(reason: string): string {
  if (reason in REASON_LABELS) return REASON_LABELS[reason]
  const [key, value] = reason.split(':')
  if (key === 'name_similarity' && value) return `${Math.round(Number(value) * 100)}% similar name`
  if (key === 'image_phash_similarity' && value) return `${Math.round(Number(value) * 100)}% similar photo`
  return reason.replace(/_/g, ' ')
}

function thumbnail(product: DigitizedProduct | undefined): string | null {
  if (!product) return null
  if (product.refined_image) return getDigitizerMediaUrl(product.job_id, 'refined', product.refined_image)
  if (product.crop_image) return getDigitizerMediaUrl(product.job_id, 'products', product.crop_image)
  return null
}

function MiniProductCard({ name, image }: { name: string; image: string | null }) {
  return (
    <div className="min-w-0">
      <div className="aspect-square w-full overflow-hidden rounded bg-stone-100">
        {image ? (
          <img src={image} alt={name} className="h-full w-full object-contain" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-[10px] text-stone-400">No image</div>
        )}
      </div>
      <p className="mt-1 truncate text-sm text-stone-800">{name}</p>
    </div>
  )
}

interface DuplicateComparisonProps {
  product: DigitizedProduct
  allProducts: DigitizedProduct[]
  onMerge: (matchedId: string) => void
  onKeepSeparate: (matchedId: string) => void
  onSelectProduct: (id: string) => void
  busyMatchId: string | null
  error: string | null
}

/** For every still-unresolved match, a compact comparison with two
 * actions; details/evidence live behind "View details" so the default
 * view stays to just images, names, and the decision. A collapsed history
 * keeps resolved matches out of the way without deleting them. Renders
 * nothing when this product has no duplicate evidence at all. */
export function DuplicateComparison({
  product,
  allProducts,
  onMerge,
  onKeepSeparate,
  onSelectProduct,
  busyMatchId,
  error,
}: DuplicateComparisonProps) {
  const unresolvedMatches = product.duplicate_matches.filter((m) => m.resolution === 'unresolved')
  const resolvedMatches = product.duplicate_matches.filter((m) => m.resolution !== 'unresolved')
  const showUnresolved = unresolvedMatches.length > 0 && product.review_status !== 'merged'

  if (!showUnresolved && resolvedMatches.length === 0) return null

  return (
    <div className="space-y-2">
      {showUnresolved && (
        <section data-testid="duplicate-section">
          <p className="text-sm font-medium text-stone-800">Possible duplicate</p>

          <div className="mt-2 space-y-4">
            {unresolvedMatches.map((match) => {
              const full = allProducts.find((p) => p.id === match.matched_product_id)
              const busy = busyMatchId === match.matched_product_id
              return (
                <div key={match.matched_product_id} data-testid={`duplicate-match-${match.matched_product_id}`}>
                  <div className="grid grid-cols-2 gap-3">
                    <MiniProductCard name={product.name_en ?? '(this product)'} image={thumbnail(product)} />
                    <MiniProductCard
                      name={match.matched_name_en ?? '(matched product)'}
                      image={thumbnail(full)}
                    />
                  </div>
                  <details className="mt-1.5">
                    <summary className="cursor-pointer text-xs text-stone-400 hover:text-stone-600">
                      View details
                    </summary>
                    <div className="mt-1 grid grid-cols-2 gap-3 text-xs text-stone-500">
                      <div>
                        <p>{product.brand ?? 'No brand'}</p>
                        <p>{product.selling_mode === 'weight' ? 'By weight' : 'Per unit'}</p>
                        <p>{product.package_weight ? `${product.package_weight} kg` : '—'}</p>
                        <p>{product.barcode ?? '—'}</p>
                      </div>
                      <div>
                        <p>{full?.brand ?? 'No brand'}</p>
                        <p>{full?.selling_mode ? (full.selling_mode === 'weight' ? 'By weight' : 'Per unit') : '—'}</p>
                        <p>{full?.package_weight ? `${full.package_weight} kg` : '—'}</p>
                        <p>{full?.barcode ?? '—'}</p>
                      </div>
                      <p className="col-span-2">
                        {Math.round(Number(match.score) * 100)}% match
                        {match.reasons.length > 0 && ` — ${match.reasons.map(humanizeReason).join(', ')}`}
                      </p>
                    </div>
                  </details>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button variant="primary" size="sm" disabled={busy} onClick={() => onMerge(match.matched_product_id)}>
                      Keep current &amp; merge duplicate
                    </Button>
                    <Button variant="secondary" size="sm" disabled={busy} onClick={() => onKeepSeparate(match.matched_product_id)}>
                      Keep both
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </section>
      )}

      {resolvedMatches.length > 0 && (
        <details data-testid="resolved-duplicate-history">
          <summary className="cursor-pointer text-xs text-stone-400 hover:text-stone-600">
            Duplicate history ({resolvedMatches.length})
          </summary>
          <ul className="mt-1 space-y-1 text-xs text-stone-500">
            {resolvedMatches.map((match) =>
              match.resolution === 'merged' ? (
                // A merged-away record is locked and no longer listed
                // anywhere -- this history entry is the one place it's
                // still reachable, "contextually" from its survivor.
                <li key={match.matched_product_id}>
                  <button
                    type="button"
                    onClick={() => onSelectProduct(match.matched_product_id)}
                    className="flex items-center gap-1.5 underline decoration-stone-300 underline-offset-2 hover:text-stone-700"
                  >
                    <Badge tone="neutral">{RESOLUTION_LABEL[match.resolution]}</Badge>
                    {match.matched_name_en ?? '(matched product)'}
                  </button>
                </li>
              ) : (
                <li key={match.matched_product_id} className="flex items-center gap-1.5">
                  <Badge tone="neutral">{RESOLUTION_LABEL[match.resolution]}</Badge>
                  {match.matched_name_en ?? '(matched product)'}
                </li>
              ),
            )}
          </ul>
        </details>
      )}
    </div>
  )
}
