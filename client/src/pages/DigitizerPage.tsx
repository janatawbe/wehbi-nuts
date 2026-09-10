import { useCallback, useEffect, useState } from 'react'
import {
  DigitizerApiError,
  getDigitizerJob,
  listDigitizerJobs,
  processDigitizerJob,
  uploadDigitizerJob,
} from '../api/digitizer'
import { FileDropzone } from '../components/digitizer/FileDropzone'
import { JobDetails } from '../components/digitizer/JobDetails'
import { JobHistory } from '../components/digitizer/JobHistory'
import { SelectedFileList } from '../components/digitizer/SelectedFileList'
import {
  DIGITIZER_ALLOWED_TYPES,
  DIGITIZER_MAX_FILES,
  DIGITIZER_MAX_FILE_SIZE_BYTES,
} from '../config/digitizer'
import type { DigitizerJob } from '../types/digitizer'

function formatMaxSize(bytes: number): string {
  return `${Math.round(bytes / (1024 * 1024))} MB`
}

function validateFiles(
  incoming: File[],
  currentCount: number,
): { valid: File[]; errors: string[] } {
  const errors: string[] = []
  const valid: File[] = []
  let count = currentCount

  for (const file of incoming) {
    if (!DIGITIZER_ALLOWED_TYPES.includes(file.type)) {
      errors.push(`${file.name}: unsupported file type.`)
      continue
    }
    if (file.size > DIGITIZER_MAX_FILE_SIZE_BYTES) {
      errors.push(`${file.name}: exceeds the maximum size of ${formatMaxSize(DIGITIZER_MAX_FILE_SIZE_BYTES)}.`)
      continue
    }
    if (count >= DIGITIZER_MAX_FILES) {
      errors.push(`${file.name}: maximum of ${DIGITIZER_MAX_FILES} images per job reached.`)
      continue
    }
    valid.push(file)
    count += 1
  }

  return { valid, errors }
}

export function DigitizerPage() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [fileErrors, setFileErrors] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [successJob, setSuccessJob] = useState<DigitizerJob | null>(null)
  const [jobs, setJobs] = useState<DigitizerJob[]>([])
  const [jobsLoading, setJobsLoading] = useState(true)
  const [jobsError, setJobsError] = useState<string | null>(null)

  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [selectedJob, setSelectedJob] = useState<DigitizerJob | null>(null)
  const [jobDetailsLoading, setJobDetailsLoading] = useState(false)
  const [jobDetailsError, setJobDetailsError] = useState<string | null>(null)
  const [processing, setProcessing] = useState(false)
  const [processError, setProcessError] = useState<string | null>(null)

  const refreshJobs = useCallback(async () => {
    setJobsLoading(true)
    setJobsError(null)
    try {
      const data = await listDigitizerJobs()
      setJobs(data)
    } catch (err) {
      setJobsError(err instanceof DigitizerApiError ? err.message : 'Could not load job history.')
    } finally {
      setJobsLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshJobs()
  }, [refreshJobs])

  const handleSelectJob = useCallback(async (jobId: string) => {
    setSelectedJobId(jobId)
    setProcessError(null)
    setJobDetailsLoading(true)
    setJobDetailsError(null)
    try {
      const job = await getDigitizerJob(jobId)
      setSelectedJob(job)
    } catch (err) {
      setSelectedJob(null)
      setJobDetailsError(
        err instanceof DigitizerApiError ? err.message : 'Could not load job details.',
      )
    } finally {
      setJobDetailsLoading(false)
    }
  }, [])

  const handleProcess = async () => {
    if (!selectedJobId || processing) return

    setProcessing(true)
    setProcessError(null)
    try {
      const job = await processDigitizerJob(selectedJobId)
      setSelectedJob(job)
      await refreshJobs()
    } catch (err) {
      setProcessError(
        err instanceof DigitizerApiError ? err.message : 'Processing failed. Please try again.',
      )
    } finally {
      setProcessing(false)
    }
  }

  const handleFilesSelected = (incoming: File[]) => {
    const { valid, errors } = validateFiles(incoming, selectedFiles.length)
    setFileErrors(errors)
    if (valid.length > 0) {
      setSelectedFiles((prev) => [...prev, ...valid])
    }
    setSuccessJob(null)
  }

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async () => {
    if (uploading || selectedFiles.length === 0) return

    setUploading(true)
    setUploadError(null)
    try {
      const job = await uploadDigitizerJob(selectedFiles)
      setSuccessJob(job)
      setSelectedFiles([])
      setFileErrors([])
      await refreshJobs()
    } catch (err) {
      setUploadError(err instanceof DigitizerApiError ? err.message : 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="min-h-dvh bg-stone-50 px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-3xl font-bold text-stone-900">Wehbi Nuts</h1>
        <p className="mt-1 text-stone-600">E-commerce Store: coming in a future milestone.</p>

        <section className="mt-8 rounded-lg border border-stone-200 bg-white p-4 shadow-sm sm:p-6">
          <h2 className="text-xl font-semibold text-stone-900">AI Product Digitizer</h2>
          <p className="mt-1 text-sm text-stone-600">
            Upload shelf or product photos to create a digitization job. Once uploaded, select the
            job below and process it with AI to detect sellable products and review the
            results.
          </p>

          <div className="mt-4">
            <FileDropzone onFilesSelected={handleFilesSelected} disabled={uploading} />
          </div>

          {fileErrors.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm text-red-600" data-testid="file-errors">
              {fileErrors.map((message) => (
                <li key={message} className="break-words">
                  {message}
                </li>
              ))}
            </ul>
          )}

          <SelectedFileList files={selectedFiles} onRemove={handleRemoveFile} disabled={uploading} />

          {selectedFiles.length > 0 && (
            <p className="mt-2 text-sm text-stone-500">
              {selectedFiles.length} image{selectedFiles.length === 1 ? '' : 's'} selected
            </p>
          )}

          <button
            type="button"
            onClick={handleSubmit}
            disabled={uploading || selectedFiles.length === 0}
            className="mt-4 w-full rounded-md bg-emerald-600 px-4 py-2.5 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
          >
            {uploading ? 'Uploading...' : 'Upload photos'}
          </button>

          {uploadError && (
            <p className="mt-3 break-words text-sm text-red-600" data-testid="upload-error">
              {uploadError}
            </p>
          )}

          {successJob && (
            <p className="mt-3 text-sm text-emerald-700" data-testid="upload-success">
              Job created ({successJob.total_items} image
              {successJob.total_items === 1 ? '' : 's'}). Status: {successJob.status}.
            </p>
          )}
        </section>

        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <section className="min-w-0 rounded-lg border border-stone-200 bg-white p-4 shadow-sm sm:p-6 lg:col-span-1">
            <h2 className="text-lg font-semibold text-stone-900">Recent digitization jobs</h2>
            <p className="mt-1 text-sm text-stone-500">Select a job to view its details and process it.</p>
            <JobHistory
              jobs={jobs}
              loading={jobsLoading}
              error={jobsError}
              selectedJobId={selectedJobId}
              onSelect={handleSelectJob}
            />
          </section>

          <section className="min-w-0 rounded-lg border border-stone-200 bg-white p-4 shadow-sm sm:p-6 lg:col-span-2">
            <h2 className="text-lg font-semibold text-stone-900">Job details</h2>
            <JobDetails
              job={selectedJob}
              loading={jobDetailsLoading}
              error={jobDetailsError}
              processing={processing}
              processError={processError}
              onProcess={handleProcess}
            />
          </section>
        </div>
      </div>
    </div>
  )
}
