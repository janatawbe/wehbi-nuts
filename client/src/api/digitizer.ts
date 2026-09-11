import { API_BASE_URL } from '../config/api'
import type { DigitizedProduct, DigitizerJob } from '../types/digitizer'

export class DigitizerApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'DigitizerApiError'
    this.status = status
  }
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json()
    if (
      data &&
      typeof data === 'object' &&
      'detail' in data &&
      typeof (data as { detail: unknown }).detail === 'string'
    ) {
      return (data as { detail: string }).detail
    }
  } catch {
    // Response body wasn't JSON; fall through to the generic message.
  }
  return `Request failed with status ${response.status}.`
}

/** JSON-only fetch wrapper shared by the job-scoped POST endpoints below
 * (process/refine-job/detect-duplicates) -- they all take no body and
 * return the updated DigitizerJob. */
async function postForJob(path: string): Promise<DigitizerJob> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: 'POST' })
  if (!response.ok) {
    throw new DigitizerApiError(await parseErrorMessage(response), response.status)
  }
  return (await response.json()) as DigitizerJob
}

export async function uploadDigitizerJob(files: File[]): Promise<DigitizerJob> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))

  // Do not set Content-Type manually: the browser must generate the
  // multipart boundary itself.
  const response = await fetch(`${API_BASE_URL}/api/digitizer/jobs`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new DigitizerApiError(await parseErrorMessage(response), response.status)
  }

  return (await response.json()) as DigitizerJob
}

export async function listDigitizerJobs(): Promise<DigitizerJob[]> {
  const response = await fetch(`${API_BASE_URL}/api/digitizer/jobs`)

  if (!response.ok) {
    throw new DigitizerApiError(await parseErrorMessage(response), response.status)
  }

  return (await response.json()) as DigitizerJob[]
}

export async function getDigitizerJob(jobId: string): Promise<DigitizerJob> {
  const response = await fetch(`${API_BASE_URL}/api/digitizer/jobs/${jobId}`)

  if (!response.ok) {
    throw new DigitizerApiError(await parseErrorMessage(response), response.status)
  }

  return (await response.json()) as DigitizerJob
}

export async function processDigitizerJob(jobId: string): Promise<DigitizerJob> {
  return postForJob(`/api/digitizer/jobs/${jobId}/process`)
}

export async function enrichDigitizedProduct(productId: string): Promise<DigitizedProduct> {
  const response = await fetch(`${API_BASE_URL}/api/digitizer/products/${productId}/enrich`, {
    method: 'POST',
  })

  if (!response.ok) {
    throw new DigitizerApiError(await parseErrorMessage(response), response.status)
  }

  return (await response.json()) as DigitizedProduct
}

// --- Milestone 6: image refinement ----------------------------------------

export async function refineDigitizedProduct(productId: string): Promise<DigitizedProduct> {
  const response = await fetch(`${API_BASE_URL}/api/digitizer/products/${productId}/refine`, {
    method: 'POST',
  })

  if (!response.ok) {
    throw new DigitizerApiError(await parseErrorMessage(response), response.status)
  }

  return (await response.json()) as DigitizedProduct
}

export async function refineDigitizerJob(jobId: string): Promise<DigitizerJob> {
  return postForJob(`/api/digitizer/jobs/${jobId}/refine`)
}

// --- Milestone 6: duplicate detection (within-job only, flags only) -------

export async function detectDigitizerJobDuplicates(jobId: string): Promise<DigitizerJob> {
  return postForJob(`/api/digitizer/jobs/${jobId}/detect-duplicates`)
}

/** Builds a displayable URL for a job's source, crop, or refined image via
 * the backend's safe media endpoint -- never construct a filesystem path
 * on the client, the filename is always the server-generated name already
 * returned by the API. */
export function getDigitizerMediaUrl(
  jobId: string,
  kind: 'source' | 'products' | 'refined',
  filename: string,
): string {
  return `${API_BASE_URL}/api/digitizer/jobs/${jobId}/media/${kind}/${filename}`
}
