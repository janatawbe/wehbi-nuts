import type { DigitizerJob } from '../../types/digitizer'

interface JobHistoryProps {
  jobs: DigitizerJob[]
  loading?: boolean
  error?: string | null
  selectedJobId?: string | null
  onSelect?: (jobId: string) => void
}

export function JobHistory({
  jobs,
  loading = false,
  error = null,
  selectedJobId = null,
  onSelect,
}: JobHistoryProps) {
  if (loading) {
    return <p className="text-sm text-stone-500">Loading job history...</p>
  }

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>
  }

  if (jobs.length === 0) {
    return <p className="text-sm text-stone-500">No digitization jobs yet.</p>
  }

  return (
    <ul className="mt-3 divide-y divide-stone-200" data-testid="job-history-list">
      {jobs.map((job) => (
        <li key={job.id}>
          <button
            type="button"
            onClick={() => onSelect?.(job.id)}
            aria-pressed={job.id === selectedJobId}
            className={`flex w-full flex-col gap-1 py-3 text-left text-sm hover:bg-stone-50 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-2 sm:py-2 ${
              job.id === selectedJobId ? 'bg-emerald-50' : ''
            }`}
          >
            <span className="flex items-center justify-between gap-2 sm:contents">
              <span className="font-mono text-stone-500">{job.id.slice(0, 8)}</span>
              <span className="capitalize">{job.status}</span>
            </span>
            <span className="flex items-center justify-between gap-2 sm:contents">
              <span>
                {job.total_items} image{job.total_items === 1 ? '' : 's'}
              </span>
              <span className="text-stone-500">{new Date(job.created_at).toLocaleString()}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}
