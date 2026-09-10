import { getDigitizerMediaUrl } from '../../api/digitizer'
import type { DigitizerJob, DigitizedProduct } from '../../types/digitizer'

interface JobDetailsProps {
  job: DigitizerJob | null
  loading: boolean
  error: string | null
  processing: boolean
  processError: string | null
  onProcess: () => void
}

const PROCESSABLE_STATUSES = new Set(['pending', 'failed'])

function ProductCard({ jobId, product }: { jobId: string; product: DigitizedProduct }) {
  return (
    <li
      className="min-w-0 rounded-md border border-stone-200 p-3"
      data-testid="digitized-product"
    >
      {product.crop_image && (
        <img
          src={getDigitizerMediaUrl(jobId, 'products', product.crop_image)}
          alt={product.name_en ?? 'Detected product'}
          className="mb-2 h-32 w-full rounded object-contain bg-stone-100"
        />
      )}
      <p className="break-words font-medium text-stone-900">{product.name_en ?? 'Unnamed product'}</p>
      {product.name_ar && (
        <p dir="rtl" lang="ar" className="break-words text-stone-700">
          {product.name_ar}
        </p>
      )}
      <dl className="mt-2 space-y-0.5 text-xs text-stone-600">
        {product.category_suggestion && (
          <div className="break-words">
            <dt className="inline font-medium">Category: </dt>
            <dd className="inline">{product.category_suggestion}</dd>
          </div>
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
      </dl>
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

  return (
    <div className="mt-3" data-testid="job-details">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-2">
        <p className="text-sm">
          Status: <span className="font-medium capitalize">{job.status}</span>
          {' -- '}
          {job.processed_items}/{job.total_items} processed
          {job.failed_items > 0 && `, ${job.failed_items} failed`}
        </p>
        {canProcess && (
          <button
            type="button"
            onClick={onProcess}
            className="w-full rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
          >
            Process with AI
          </button>
        )}
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
                <ProductCard key={product.id} jobId={job.id} product={product} />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
