import type { DigitizerJob } from '../../types/digitizer'

interface JobHistoryProps {
  jobs: DigitizerJob[]
  loading?: boolean
  error?: string | null
  selectedJobId?: string | null
  onSelect?: (jobId: string) => void
}

const JOB_STATUS_LABELS: Record<string, string> = {
  pending: 'Waiting',
  processing: 'Processing',
  completed: 'Ready',
  failed: 'Needs attention',
}

export function JobHistory({
  jobs,
  loading = false,
  error = null,
  selectedJobId = null,
  onSelect,
}: JobHistoryProps) {
  if (loading) {
    return <p className="text-sm text-stone-500">Loading...</p>
  }

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>
  }

  if (jobs.length === 0) {
    return <p className="text-sm text-stone-500">No uploads yet.</p>
  }

  return (
    <ul className="divide-y divide-stone-100" data-testid="job-history-list">
      {jobs.map((job) => {
        const isSelected = job.id === selectedJobId
        return (
          <li key={job.id}>
            <button
              type="button"
              onClick={() => onSelect?.(job.id)}
              aria-pressed={isSelected}
              data-testid={`job-history-item-${job.id}`}
              className={`flex w-full items-center justify-between gap-3 px-1 py-2.5 text-left text-sm hover:bg-stone-50 ${
                isSelected ? 'bg-stone-50' : ''
              }`}
            >
              <span className="text-stone-700">{new Date(job.created_at).toLocaleDateString()}</span>
              <span className="text-stone-500">
                {job.total_items} image{job.total_items === 1 ? '' : 's'}
              </span>
              <span className="text-stone-500">{JOB_STATUS_LABELS[job.status] ?? job.status}</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
