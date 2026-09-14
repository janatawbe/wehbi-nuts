import { API_BASE_URL } from '../config/api'
import type { CatalogImportPreview, CatalogImportResult } from '../types/catalog'

export class CatalogApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'CatalogApiError'
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

async function fetchBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new CatalogApiError(await parseErrorMessage(response), response.status)
  }
  return response.blob()
}

export function exportCatalogXlsx(): Promise<Blob> {
  return fetchBlob('/api/catalog/export.xlsx')
}

async function postFile<T>(path: string, file: File): Promise<T> {
  const formData = new FormData()
  formData.append('file', file)

  // Do not set Content-Type manually: the browser must generate the
  // multipart boundary itself.
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new CatalogApiError(await parseErrorMessage(response), response.status)
  }

  return (await response.json()) as T
}

export function previewCatalogImport(file: File): Promise<CatalogImportPreview> {
  return postFile<CatalogImportPreview>('/api/catalog/import/preview', file)
}

export function confirmCatalogImport(file: File): Promise<CatalogImportResult> {
  return postFile<CatalogImportResult>('/api/catalog/import/confirm', file)
}

/** Saves a Blob to the user's device via a throwaway object URL -- the
 * only reasonably portable way to trigger a browser download from an
 * in-memory response body without a real anchor href to a static file. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
