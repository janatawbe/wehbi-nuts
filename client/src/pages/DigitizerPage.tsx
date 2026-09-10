import { useCallback, useEffect, useState } from 'react'
import { DigitizerApiError, listDigitizerJobs, uploadDigitizerJob } from '../api/digitizer'
import { FileDropzone } from '../components/digitizer/FileDropzone'
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
    <div className="min-h-screen bg-stone-50 px-6 py-10">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-3xl font-bold text-stone-900">Wehbi Nuts</h1>
        <p className="mt-1 text-stone-600">E-commerce Store: coming in a future milestone.</p>

        <section className="mt-8 rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-stone-900">AI Product Digitizer</h2>
          <p className="mt-1 text-sm text-stone-600">
            Upload shelf or product photos to start digitizing them. This step only uploads your
            photos and creates a digitization job -- automatic product recognition happens in a
            later milestone.
          </p>

          <div className="mt-4">
            <FileDropzone onFilesSelected={handleFilesSelected} disabled={uploading} />
          </div>

          {fileErrors.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm text-red-600" data-testid="file-errors">
              {fileErrors.map((message) => (
                <li key={message}>{message}</li>
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
            className="mt-4 rounded-md bg-emerald-600 px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploading ? 'Uploading...' : 'Upload photos'}
          </button>

          {uploadError && (
            <p className="mt-3 text-sm text-red-600" data-testid="upload-error">
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

        <section className="mt-8 rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-stone-900">Recent digitization jobs</h2>
          <JobHistory jobs={jobs} loading={jobsLoading} error={jobsError} />
        </section>
      </div>
    </div>
  )
}
