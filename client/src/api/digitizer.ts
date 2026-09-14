import { API_BASE_URL } from '../config/api'
import type {
  BulkApproveResponse,
  Category,
  DigitizedProduct,
  DigitizedProductReviewUpdate,
  DigitizerJob,
  DuplicateMergeResponse,
} from '../types/digitizer'

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

/** Convenience wrapper for the existing job-level enrich endpoint
 * (`POST /api/digitizer/jobs/{id}/enrich`, already implemented server-side
 * since Milestone 5) -- added so the renovated UI can offer a single
 * "Enrich Products" next-action button instead of forcing a first-time
 * user to click "Enrich" on every card individually. No backend change. */
export async function enrichDigitizerJob(jobId: string): Promise<DigitizerJob> {
  return postForJob(`/api/digitizer/jobs/${jobId}/enrich`)
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

export async function listCategories(): Promise<Category[]> {
  const response = await fetch(`${API_BASE_URL}/api/digitizer/categories`)

  if (!response.ok) {
    throw new DigitizerApiError(await parseErrorMessage(response), response.status)
  }

  return (await response.json()) as Category[]
}

// --- Milestone 7: human review & approval -----------------------------

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    throw new DigitizerApiError(await parseErrorMessage(response), response.status)
  }

  return (await response.json()) as T
}

export async function listAllDigitizedProducts(): Promise<DigitizedProduct[]> {
  const response = await fetch(`${API_BASE_URL}/api/digitizer/products`)

  if (!response.ok) {
    throw new DigitizerApiError(await parseErrorMessage(response), response.status)
  }

  return (await response.json()) as DigitizedProduct[]
}

export async function updateDigitizedProductReview(
  productId: string,
  payload: DigitizedProductReviewUpdate,
): Promise<DigitizedProduct> {
  const response = await fetch(`${API_BASE_URL}/api/digitizer/products/${productId}/review`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new DigitizerApiError(await parseErrorMessage(response), response.status)
  }

  return (await response.json()) as DigitizedProduct
}

export async function approveDigitizedProduct(productId: string): Promise<DigitizedProduct> {
  return postJson<DigitizedProduct>(`/api/digitizer/products/${productId}/approve`)
}

export async function rejectDigitizedProduct(
  productId: string,
  reason?: string,
): Promise<DigitizedProduct> {
  return postJson<DigitizedProduct>(
    `/api/digitizer/products/${productId}/reject`,
    reason ? { reason } : undefined,
  )
}

export async function keepDigitizedProductsSeparate(
  productIds: string[],
): Promise<DigitizedProduct[]> {
  return postJson<DigitizedProduct[]>('/api/digitizer/products/duplicates/keep-separate', {
    product_ids: productIds,
  })
}

export async function mergeDigitizedProducts(
  canonicalId: string,
  mergeIds: string[],
): Promise<DuplicateMergeResponse> {
  return postJson<DuplicateMergeResponse>('/api/digitizer/products/duplicates/merge', {
    canonical_id: canonicalId,
    merge_ids: mergeIds,
  })
}

export async function bulkApproveDigitizedProducts(
  productIds: string[],
): Promise<BulkApproveResponse> {
  return postJson<BulkApproveResponse>('/api/digitizer/products/bulk-approve', {
    product_ids: productIds,
  })
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
