import type { DigitizerJob } from '../../types/digitizer'
import { Button } from '../ui/Button'
import { computeJobStatus, type NextAction } from './JobStatus'
import { ProductCandidateCard } from './ProductCandidateCard'

interface JobDetailsProps {
  job: DigitizerJob | null
  loading: boolean
  error: string | null

  actionBusy: boolean
  actionError: string | null
  onAction: (action: NextAction) => void

  enrichingProductId: string | null
  enrichErrors: Record<string, string>
  onEnrichProduct: (productId: string) => void

  refiningProductId: string | null
  refineErrors: Record<string, string>
  onRefineProduct: (productId: string) => void
}

export function JobDetails({
  job,
  loading,
  error,
  actionBusy,
  actionError,
  onAction,
  enrichingProductId,
  enrichErrors,
  onEnrichProduct,
  refiningProductId,
  refineErrors,
  onRefineProduct,
}: JobDetailsProps) {
  if (loading) {
    return <p className="mt-3 text-sm text-stone-500">Loading...</p>
  }

  if (error) {
    return (
      <p className="mt-3 break-words text-sm text-red-600" data-testid="job-details-error">
        {error}
      </p>
    )
  }

  if (!job) {
    return <p className="mt-3 text-sm text-stone-500">Select a job to see its progress.</p>
  }

  const { message, nextAction } = computeJobStatus(job)
  const showError = job.error_message && (job.status === 'failed' || job.failed_items > 0)

  return (
    <div className="mt-3 space-y-4" data-testid="job-details">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-stone-700">{actionBusy ? 'Preparing products...' : message}</p>
        {nextAction && (
          <Button variant="primary" size="sm" disabled={actionBusy} onClick={() => onAction(nextAction)}>
            {actionBusy ? 'Working...' : nextAction.label}
          </Button>
        )}
      </div>

      {actionError && (
        <p className="break-words text-sm text-red-600" data-testid="job-action-error">
          {actionError}
        </p>
      )}
      {showError && (
        <p className="break-words text-sm text-red-600" data-testid="job-error-message">
          {job.error_message}
        </p>
      )}

      {job.status === 'completed' && job.candidates.length > 0 && (
        <ul className="grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-3" data-testid="digitized-products-list">
          {job.candidates.map((product) => (
            <ProductCandidateCard
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
  )
}
