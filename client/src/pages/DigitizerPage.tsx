import { useCallback, useEffect, useState } from 'react'
import {
  DigitizerApiError,
  detectDigitizerJobDuplicates,
  enrichDigitizedProduct,
  enrichDigitizerJob,
  getDigitizerJob,
  listDigitizerJobs,
  processDigitizerJob,
  refineDigitizedProduct,
  refineDigitizerJob,
  uploadDigitizerJob,
} from '../api/digitizer'
import { FileDropzone } from '../components/digitizer/FileDropzone'
import { JobDetails } from '../components/digitizer/JobDetails'
import { JobHistory } from '../components/digitizer/JobHistory'
import type { NextAction } from '../components/digitizer/JobStatus'
import { SelectedFileList } from '../components/digitizer/SelectedFileList'
import { Button } from '../components/ui/Button'
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
  const [jobs, setJobs] = useState<DigitizerJob[]>([])
  const [jobsLoading, setJobsLoading] = useState(true)
  const [jobsError, setJobsError] = useState<string | null>(null)

  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [selectedJob, setSelectedJob] = useState<DigitizerJob | null>(null)
  const [jobDetailsLoading, setJobDetailsLoading] = useState(false)
  const [jobDetailsError, setJobDetailsError] = useState<string | null>(null)

  const [actionBusy, setActionBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const [enrichingProductId, setEnrichingProductId] = useState<string | null>(null)
  const [enrichErrors, setEnrichErrors] = useState<Record<string, string>>({})
  const [refiningProductId, setRefiningProductId] = useState<string | null>(null)
  const [refineErrors, setRefineErrors] = useState<Record<string, string>>({})

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
    setActionError(null)
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

  const handleAction = async (action: NextAction) => {
    if (!action || !selectedJobId || actionBusy) return

    setActionBusy(true)
    setActionError(null)
    try {
      switch (action.key) {
        case 'process': {
          const job = await processDigitizerJob(selectedJobId)
          setSelectedJob(job)
          await refreshJobs()
          break
        }
        case 'enrich':
          setSelectedJob(await enrichDigitizerJob(selectedJobId))
          break
        case 'refine':
          setSelectedJob(await refineDigitizerJob(selectedJobId))
          break
        case 'detect_duplicates':
          setSelectedJob(await detectDigitizerJobDuplicates(selectedJobId))
          break
      }
    } catch (err) {
      setActionError(err instanceof DigitizerApiError ? err.message : 'That action failed. Please try again.')
    } finally {
      setActionBusy(false)
    }
  }

  const handleEnrichProduct = async (productId: string) => {
    if (enrichingProductId) return

    setEnrichingProductId(productId)
    setEnrichErrors((prev) => {
      const next = { ...prev }
      delete next[productId]
      return next
    })
    try {
      const enriched = await enrichDigitizedProduct(productId)
      setSelectedJob((prev) =>
        prev
          ? {
              ...prev,
              candidates: prev.candidates.map((candidate) =>
                candidate.id === productId ? enriched : candidate,
              ),
            }
          : prev,
      )
    } catch (err) {
      setEnrichErrors((prev) => ({
        ...prev,
        [productId]: err instanceof DigitizerApiError ? err.message : 'That failed. Please try again.',
      }))
    } finally {
      setEnrichingProductId(null)
    }
  }

  const handleRefineProduct = async (productId: string) => {
    if (refiningProductId) return

    setRefiningProductId(productId)
    setRefineErrors((prev) => {
      const next = { ...prev }
      delete next[productId]
      return next
    })
    try {
      const refined = await refineDigitizedProduct(productId)
      setSelectedJob((prev) =>
        prev
          ? {
              ...prev,
              candidates: prev.candidates.map((candidate) =>
                candidate.id === productId ? refined : candidate,
              ),
            }
          : prev,
      )
    } catch (err) {
      setRefineErrors((prev) => ({
        ...prev,
        [productId]: err instanceof DigitizerApiError ? err.message : 'That failed. Please try again.',
      }))
    } finally {
      setRefiningProductId(null)
    }
  }

  const handleFilesSelected = (incoming: File[]) => {
    const { valid, errors } = validateFiles(incoming, selectedFiles.length)
    setFileErrors(errors)
    if (valid.length > 0) {
      setSelectedFiles((prev) => [...prev, ...valid])
    }
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
      setSelectedFiles([])
      setFileErrors([])
      await refreshJobs()
      await handleSelectJob(job.id)
    } catch (err) {
      setUploadError(err instanceof DigitizerApiError ? err.message : 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="min-h-dvh bg-cream px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-xl font-semibold text-stone-900">AI Product Digitizer</h1>

        <div className="mt-5">
          <FileDropzone onFilesSelected={handleFilesSelected} disabled={uploading} />

          {fileErrors.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm text-red-600" data-testid="file-errors">
              {fileErrors.map((message) => (
                <li key={message} className="break-words">
                  {message}
                </li>
              ))}
            </ul>
          )}

          <SelectedFileList files={selectedFiles} onRemove={handleRemoveFile} disabled={uploading} />

          {selectedFiles.length > 0 && (
            <Button variant="primary" className="mt-3" onClick={handleSubmit} disabled={uploading}>
              {uploading ? 'Uploading...' : 'Upload Photos'}
            </Button>
          )}

          {uploadError && (
            <p className="mt-2 break-words text-sm text-red-600" data-testid="upload-error">
              {uploadError}
            </p>
          )}
        </div>

        <div className="mt-10">
          <h2 className="text-sm font-medium text-stone-500">Recent Jobs</h2>
          <div className="mt-2">
            <JobHistory
              jobs={jobs}
              loading={jobsLoading}
              error={jobsError}
              selectedJobId={selectedJobId}
              onSelect={handleSelectJob}
            />
          </div>
        </div>

        {selectedJobId && (
          <div className="mt-8 border-t border-stone-200 pt-6">
            <JobDetails
              job={selectedJob}
              loading={jobDetailsLoading}
              error={jobDetailsError}
              actionBusy={actionBusy}
              actionError={actionError}
              onAction={handleAction}
              enrichingProductId={enrichingProductId}
              enrichErrors={enrichErrors}
              onEnrichProduct={handleEnrichProduct}
              refiningProductId={refiningProductId}
              refineErrors={refineErrors}
              onRefineProduct={handleRefineProduct}
            />
          </div>
        )}
      </div>
    </div>
  )
}
