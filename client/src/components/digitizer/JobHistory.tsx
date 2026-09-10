import type { DigitizerJob } from '../../types/digitizer'

interface JobHistoryProps {
  jobs: DigitizerJob[]
  loading?: boolean
  error?: string | null
}

export function JobHistory({ jobs, loading = false, error = null }: JobHistoryProps) {
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
        <li key={job.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
          <span className="font-mono text-stone-500">{job.id.slice(0, 8)}</span>
          <span className="capitalize">{job.status}</span>
          <span>
            {job.total_items} image{job.total_items === 1 ? '' : 's'}
          </span>
          <span className="text-stone-500">{new Date(job.created_at).toLocaleString()}</span>
        </li>
      ))}
    </ul>
  )
}
