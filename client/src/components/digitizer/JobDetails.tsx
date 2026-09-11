import { useState } from 'react'
import { getDigitizerMediaUrl } from '../../api/digitizer'
import type { DigitizerJob, DigitizedProduct } from '../../types/digitizer'

interface JobDetailsProps {
  job: DigitizerJob | null
  loading: boolean
  error: string | null
  processing: boolean
  processError: string | null
  onProcess: () => void
  enrichingProductId: string | null
  enrichErrors: Record<string, string>
  onEnrichProduct: (productId: string) => void
  refiningProductId: string | null
  refineErrors: Record<string, string>
  onRefineProduct: (productId: string) => void
  detectingDuplicates: boolean
  duplicatesError: string | null
  onDetectDuplicates: () => void
}

const PROCESSABLE_STATUSES = new Set(['pending', 'failed'])

const SELLING_MODE_LABELS: Record<string, string> = {
  weight: 'By weight',
  unit: 'Per unit',
}

const DUPLICATE_STATUS_LABELS: Record<string, string> = {
  likely: 'Likely duplicate',
  possible: 'Possible duplicate',
}

/** A field's value plus a "needs review" badge when its field_review entry
 * flags it -- display-only (full edit/approve UI is Milestone 7), matching
 * the read-only pattern the other AI-derived fields below already use. */
function ReviewableField({
  label,
  value,
  fieldKey,
  fieldReview,
}: {
  label: string
  value: string
  fieldKey: string
  fieldReview: DigitizedProduct['field_review']
}) {
  const needsReview = fieldReview?.[fieldKey]?.needs_review ?? false
  return (
    <div className={`break-words ${needsReview ? 'rounded border border-amber-400 bg-amber-50 px-1' : ''}`}>
      <dt className="inline font-medium">{label}: </dt>
      <dd className="inline">{value}</dd>
      {needsReview && (
        <span className="ml-1 inline-block rounded bg-amber-200 px-1 text-[10px] font-semibold uppercase text-amber-900">
          needs review
        </span>
      )}
    </div>
  )
}

/** Shows the M6 refined catalog image when one exists (falling back to the
 * M4 crop otherwise), with a small toggle to compare it against the
 * original crop -- both files always exist independently on the backend,
 * this is purely a display choice. */
function ProductImage({ jobId, product }: { jobId: string; product: DigitizedProduct }) {
  const hasRefined = product.refined_image !== null
  const [showOriginal, setShowOriginal] = useState(false)

  const showingRefined = hasRefined && !showOriginal
  const filename = showingRefined ? product.refined_image : product.crop_image
  if (!filename) {
    return null
  }

  return (
    <div className="mb-2">
      <img
        src={getDigitizerMediaUrl(jobId, showingRefined ? 'refined' : 'products', filename)}
        alt={product.name_en ?? 'Detected product'}
        className="h-32 w-full rounded object-contain bg-stone-100"
      />
      {hasRefined && (
        <button
          type="button"
          onClick={() => setShowOriginal((prev) => !prev)}
          className="mt-1 text-[11px] font-medium text-sky-700 underline"
          data-testid="toggle-image-view"
        >
          {showOriginal ? 'Show refined image' : 'Show original crop'}
        </button>
      )}
    </div>
  )
}

/** Milestone 6 duplicate-detection evidence, display-only -- no Merge/Keep
 * Separate action here, that decision belongs to Milestone 7. Shows the
 * strongest match (duplicate_matches is already score-sorted by the API). */
function DuplicateBadge({ product }: { product: DigitizedProduct }) {
  if (product.duplicate_status !== 'possible' && product.duplicate_status !== 'likely') {
    return null
  }
  const bestMatch = product.duplicate_matches[0]
  return (
    <div
      className="mt-2 rounded border border-amber-400 bg-amber-50 px-2 py-1 text-xs text-amber-900"
      data-testid="duplicate-badge"
    >
      <p className="font-semibold">{DUPLICATE_STATUS_LABELS[product.duplicate_status]}</p>
      {bestMatch && (
        <p>
          {Math.round(Number(bestMatch.score) * 100)}% match -- Matches:{' '}
          {bestMatch.matched_name_en ?? 'another detected product'}
        </p>
      )}
    </div>
  )
}

function ProductCard({
  jobId,
  product,
  enriching,
  enrichError,
  onEnrich,
  refining,
  refineError,
  onRefine,
}: {
  jobId: string
  product: DigitizedProduct
  enriching: boolean
  enrichError: string | null
  onEnrich: () => void
  refining: boolean
  refineError: string | null
  onRefine: () => void
}) {
  const fieldReview = product.field_review
  const isEnriched = fieldReview !== null
  const isRefined = product.image_refinement_status === 'refined'

  return (
    <li
      className="min-w-0 rounded-md border border-stone-200 p-3"
      data-testid="digitized-product"
    >
      <ProductImage jobId={jobId} product={product} />
      <p className="break-words font-medium text-stone-900">{product.name_en ?? 'Unnamed product'}</p>
      {product.name_ar && (
        <p dir="rtl" lang="ar" className="break-words text-stone-700">
          {product.name_ar}
        </p>
      )}
      <DuplicateBadge product={product} />
      <dl className="mt-2 space-y-0.5 text-xs text-stone-600">
        {isEnriched ? (
          <ReviewableField
            label="Category"
            fieldKey="category"
            fieldReview={fieldReview}
            value={product.category_id ? (product.category_suggestion ?? 'Resolved') : 'Unresolved -- needs category'}
          />
        ) : (
          product.category_suggestion && (
            <div className="break-words">
              <dt className="inline font-medium">Category: </dt>
              <dd className="inline">{product.category_suggestion}</dd>
            </div>
          )
        )}
        {product.presentation && (
          <div className="break-words">
            <dt className="inline font-medium">Presentation: </dt>
            <dd className="inline">{product.presentation}</dd>
          </div>
        )}
        {product.ai_confidence && (
          <div className="break-words">
            <dt className="inline font-medium">Confidence: </dt>
            <dd className="inline">{Math.round(Number(product.ai_confidence) * 100)}%</dd>
          </div>
        )}
        {product.identification_basis && (
          <div className="break-words">
            <dt className="inline font-medium">Identification basis: </dt>
            <dd className="inline">{product.identification_basis.replace(/_/g, ' ')}</dd>
          </div>
        )}
        {product.visible_text && (
          <div className="break-words">
            <dt className="inline font-medium">Visible text: </dt>
            <dd className="inline">{product.visible_text}</dd>
          </div>
        )}
        {product.notes && (
          <div className="break-words">
            <dt className="inline font-medium">Notes: </dt>
            <dd className="inline">{product.notes}</dd>
          </div>
        )}

        {isEnriched && (
          <>
            <ReviewableField
              label="Selling mode"
              fieldKey="selling_mode"
              fieldReview={fieldReview}
              value={
                product.selling_mode
                  ? (SELLING_MODE_LABELS[product.selling_mode] ?? product.selling_mode)
                  : 'Unknown'
              }
            />
            <ReviewableField
              label="Package weight"
              fieldKey="package_weight"
              fieldReview={fieldReview}
              value={product.package_weight ? `${product.package_weight} kg` : 'None (not packaged, or not printed)'}
            />
            <ReviewableField
              label="Brand"
              fieldKey="brand"
              fieldReview={fieldReview}
              value={product.brand ?? 'None (no visible brand)'}
            />
            <ReviewableField
              label="Flavor / variant"
              fieldKey="flavor_variant"
              fieldReview={fieldReview}
              value={product.flavor_variant ?? 'None identified'}
            />
            <ReviewableField
              label="Barcode"
              fieldKey="barcode"
              fieldReview={fieldReview}
              value={product.barcode ?? 'None (no visible barcode)'}
            />
            {product.description_en && (
              <ReviewableField
                label="Description (EN)"
                fieldKey="description_en"
                fieldReview={fieldReview}
                value={product.description_en}
              />
            )}
            {product.description_ar && (
              <ReviewableField
                label="Description (AR)"
                fieldKey="description_ar"
                fieldReview={fieldReview}
                value={product.description_ar}
              />
            )}
          </>
        )}
      </dl>

      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={onEnrich}
          disabled={enriching}
          className="w-full rounded-md border border-emerald-600 px-2 py-1 text-xs font-medium text-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          data-testid="enrich-product-button"
        >
          {enriching ? 'Enriching...' : isEnriched ? 'Re-enrich' : 'Enrich'}
        </button>
        <button
          type="button"
          onClick={onRefine}
          disabled={refining}
          className="w-full rounded-md border border-sky-600 px-2 py-1 text-xs font-medium text-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
          data-testid="refine-product-button"
        >
          {refining ? 'Refining...' : isRefined ? 'Re-refine' : 'Refine'}
        </button>
      </div>
      {enrichError && (
        <p className="mt-1 break-words text-xs text-red-600" data-testid="enrich-product-error">
          {enrichError}
        </p>
      )}
      {refineError && (
        <p className="mt-1 break-words text-xs text-red-600" data-testid="refine-product-error">
          {refineError}
        </p>
      )}
    </li>
  )
}

export function JobDetails({
  job,
  loading,
  error,
  processing,
  processError,
  onProcess,
  enrichingProductId,
  enrichErrors,
  onEnrichProduct,
  refiningProductId,
  refineErrors,
  onRefineProduct,
  detectingDuplicates,
  duplicatesError,
  onDetectDuplicates,
}: JobDetailsProps) {
  if (loading) {
    return <p className="mt-3 text-sm text-stone-500">Loading job details...</p>
  }

  if (error) {
    return (
      <p className="mt-3 break-words text-sm text-red-600" data-testid="job-details-error">
        {error}
      </p>
    )
  }

  if (!job) {
    return <p className="mt-3 text-sm text-stone-500">Select a job above to see its details.</p>
  }

  const canProcess = PROCESSABLE_STATUSES.has(job.status) && !processing
  const canDetectDuplicates = job.status === 'completed' && job.candidates.length > 0 && !detectingDuplicates

  return (
    <div className="mt-3" data-testid="job-details">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-2">
        <p className="text-sm">
          Status: <span className="font-medium capitalize">{job.status}</span>
          {' -- '}
          {job.processed_items}/{job.total_items} processed
          {job.failed_items > 0 && `, ${job.failed_items} failed`}
        </p>
        <div className="flex flex-col gap-2 sm:flex-row">
          {canProcess && (
            <button
              type="button"
              onClick={onProcess}
              className="w-full rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              Process with AI
            </button>
          )}
          {job.status === 'completed' && job.candidates.length > 0 && (
            <button
              type="button"
              onClick={onDetectDuplicates}
              disabled={!canDetectDuplicates}
              className="w-full rounded-md border border-stone-400 px-3 py-2 text-sm font-medium text-stone-700 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
              data-testid="detect-duplicates-button"
            >
              {detectingDuplicates ? 'Checking for duplicates...' : 'Detect Duplicates'}
            </button>
          )}
        </div>
      </div>

      {processing && (
        <p className="mt-2 text-sm text-emerald-700" data-testid="job-processing">
          AI is analyzing this job's images... this can take a little while.
        </p>
      )}

      {processError && (
        <p className="mt-2 break-words text-sm text-red-600" data-testid="job-process-error">
          {processError}
        </p>
      )}

      {duplicatesError && (
        <p className="mt-2 break-words text-sm text-red-600" data-testid="job-duplicates-error">
          {duplicatesError}
        </p>
      )}

      {job.status === 'completed' && job.duplicate_summary && job.duplicate_summary.skipped_not_enriched > 0 && (
        <p className="mt-2 break-words text-sm text-amber-700" data-testid="duplicate-enrichment-notice">
          {job.duplicate_summary.skipped_not_enriched} of {job.duplicate_summary.total_candidates} products
          haven't been enriched yet -- Detect Duplicates can only compare products that have been enriched.
          Enrich them for full duplicate coverage.
        </p>
      )}

      {job.status === 'completed' &&
        job.duplicate_summary &&
        job.duplicate_summary.eligible_candidates > 0 &&
        (job.duplicate_summary.possible_count > 0 || job.duplicate_summary.likely_count > 0) && (
          <p className="mt-2 text-sm text-stone-600" data-testid="duplicate-summary">
            Compared {job.duplicate_summary.eligible_candidates} enriched product
            {job.duplicate_summary.eligible_candidates === 1 ? '' : 's'}: {job.duplicate_summary.likely_count} likely
            and {job.duplicate_summary.possible_count} possible duplicate flag
            {job.duplicate_summary.likely_count + job.duplicate_summary.possible_count === 1 ? '' : 's'}.
          </p>
        )}

      {job.status === 'failed' && job.error_message && (
        <p className="mt-2 break-words text-sm text-red-600" data-testid="job-error-message">
          {job.error_message}
        </p>
      )}

      {job.status === 'completed' && job.failed_items > 0 && job.error_message && (
        <p className="mt-2 break-words text-sm text-amber-700" data-testid="job-partial-error">
          {job.error_message}
        </p>
      )}

      {job.status === 'completed' && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold text-stone-900">
            Detected products ({job.candidates.length})
          </h3>
          {job.candidates.length === 0 ? (
            <p className="mt-1 text-sm text-stone-500">No sellable products were detected.</p>
          ) : (
            <ul
              className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3"
              data-testid="digitized-products-list"
            >
              {job.candidates.map((product) => (
                <ProductCard
                  key={product.id}
                  jobId={job.id}
                  product={product}
                  enriching={enrichingProductId === product.id}
                  enrichError={enrichErrors[product.id] ?? null}
                  onEnrich={() => onEnrichProduct(product.id)}
                  refining={refiningProductId === product.id}
                  refineError={refineErrors[product.id] ?? null}
                  onRefine={() => onRefineProduct(product.id)}
                />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
