import { API_BASE_URL } from '../config/api'
import type { DigitizerJob } from '../types/digitizer'

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
