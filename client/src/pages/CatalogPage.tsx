import { useRef, useState } from 'react'
import {
  CatalogApiError,
  confirmCatalogImport,
  downloadBlob,
  exportCatalogXlsx,
  previewCatalogImport,
} from '../api/catalog'
import type { CatalogImportPreview, CatalogImportResult } from '../types/catalog'
import { Button } from '../components/ui/Button'

/** Milestone 8: a simple, admin-only Catalog page -- export the store's
 * products to Excel, edit them there, and safely bring the changes back
 * through an explicit Preview -> Confirm step. Nothing is applied to the
 * store until "Confirm Import" is clicked. Deliberately not styled as a
 * data-management dashboard -- one job, three actions: Export, Preview,
 * Confirm. */
export function CatalogPage() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [preview, setPreview] = useState<CatalogImportPreview | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const [result, setResult] = useState<CatalogImportResult | null>(null)

  const handleExport = async () => {
    setExportError(null)
    try {
      const blob = await exportCatalogXlsx()
      downloadBlob(blob, 'wehbi-nuts-catalog.xlsx')
    } catch (err) {
      setExportError(err instanceof CatalogApiError ? err.message : 'Could not export the catalog.')
    }
  }

  const reset = () => {
    setFile(null)
    setPreview(null)
    setPreviewError(null)
    setResult(null)
    setConfirmError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleFileChange = (selected: File | null) => {
    setPreview(null)
    setResult(null)
    setConfirmError(null)

    if (selected && !selected.name.toLowerCase().endsWith('.xlsx')) {
      setFile(null)
      setPreviewError('Please upload an Excel (.xlsx) file.')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    setFile(selected)
    setPreviewError(null)
  }

  const handlePreview = async () => {
    if (!file) return
    setPreviewing(true)
    setPreviewError(null)
    try {
      const nextPreview = await previewCatalogImport(file)
      setPreview(nextPreview)
    } catch (err) {
      setPreviewError(err instanceof CatalogApiError ? err.message : 'Could not read this file.')
    } finally {
      setPreviewing(false)
    }
  }

  const handleConfirm = async () => {
    if (!file) return
    setConfirming(true)
    setConfirmError(null)
    try {
      setResult(await confirmCatalogImport(file))
      setPreview(null)
    } catch (err) {
      setConfirmError(err instanceof CatalogApiError ? err.message : 'Import failed.')
    } finally {
      setConfirming(false)
    }
  }

  const showImportForm = !result

  return (
    <div className="min-h-dvh bg-cream px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-2xl space-y-8">
        <div>
          <h1 className="text-xl font-semibold text-stone-900">Catalog</h1>
          <p className="mt-1 text-sm text-stone-500">
            Manage your store products using Excel. Export your current catalog, make changes or add
            products, then import it back to update the store.
          </p>
        </div>

        <section className="space-y-2">
          <h2 className="text-base font-semibold text-stone-900">Export Catalog</h2>
          <p className="text-sm text-stone-500">Download your current product catalog as an Excel file.</p>
          <Button variant="secondary" onClick={handleExport}>
            Export Excel
          </Button>
          {exportError && <p className="text-sm text-red-600">{exportError}</p>}
        </section>

        <section className="space-y-3 border-t border-stone-200 pt-6">
          <h2 className="text-base font-semibold text-stone-900">Import Catalog</h2>
          <p className="text-sm text-stone-500">
            Upload an edited catalog or an Excel file containing new products.
          </p>

          {showImportForm && (
            <>
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx"
                  className="hidden"
                  data-testid="catalog-import-file-input"
                  onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
                />
                <Button variant="secondary" onClick={() => fileInputRef.current?.click()}>
                  Choose Excel File
                </Button>
              </div>

              {previewError && (
                <p className="text-sm text-red-600" data-testid="catalog-import-error">
                  {previewError}
                </p>
              )}

              {file && !preview && (
                <div className="space-y-2">
                  <p className="text-sm text-stone-700">{file.name}</p>
                  <Button variant="primary" disabled={previewing} onClick={handlePreview}>
                    {previewing ? 'Reading...' : 'Preview Import'}
                  </Button>
                </div>
              )}

              {preview && <ImportPreview preview={preview} />}

              {preview && (
                <>
                  {confirmError && (
                    <p className="text-sm text-red-600" data-testid="catalog-import-confirm-error">
                      {confirmError}
                    </p>
                  )}
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={reset}
                      className="text-sm text-stone-500 underline decoration-stone-300 underline-offset-2 hover:text-stone-700"
                    >
                      Cancel
                    </button>
                    <Button variant="primary" disabled={confirming} onClick={handleConfirm}>
                      {confirming ? 'Importing...' : 'Confirm Import'}
                    </Button>
                  </div>
                </>
              )}
            </>
          )}

          {result && <ImportResultSummary result={result} onReset={reset} />}
        </section>
      </div>
    </div>
  )
}

function ImportPreview({ preview }: { preview: CatalogImportPreview }) {
  const changedRows = preview.rows.filter((row) => row.action !== 'unchanged')
  const unchangedRows = preview.rows.filter((row) => row.action === 'unchanged')

  return (
    <div className="space-y-3 border-t border-stone-200 pt-4" data-testid="catalog-import-preview">
      <h3 className="text-sm font-semibold text-stone-900">Import Preview</h3>

      <p className="text-sm text-stone-700">
        <span className="font-medium text-stone-900">{preview.new_count}</span> New
        <span className="mx-2 text-stone-300">·</span>
        <span className="font-medium text-stone-900">{preview.update_count}</span> Updates
        <span className="mx-2 text-stone-300">·</span>
        <span className="font-medium text-stone-900">{preview.unchanged_count}</span> Unchanged
        <span className="mx-2 text-stone-300">·</span>
        <span className="font-medium text-stone-900">{preview.invalid_count}</span> Invalid
      </p>

      {changedRows.length > 0 && (
        <ul className="divide-y divide-stone-100" data-testid="catalog-import-rows">
          {changedRows.map((row) => (
            <li key={row.row_number} className="py-2 text-sm" data-testid={`catalog-import-row-${row.row_number}`}>
              <p className="font-medium text-stone-900">{row.name_en ?? row.sku ?? `Row ${row.row_number}`}</p>
              {row.action === 'new' && <p className="text-stone-500">New product</p>}
              {row.action === 'invalid' &&
                row.errors.map((reason) => (
                  <p key={reason} className="text-red-600">
                    {reason}
                  </p>
                ))}
              {row.action === 'update' &&
                row.changes.map((change) => (
                  <p key={change.field} className="text-stone-500">
                    {change.label}: {change.old ?? '—'} → {change.new ?? '—'}
                  </p>
                ))}
            </li>
          ))}
        </ul>
      )}

      {unchangedRows.length > 0 && (
        <details>
          <summary className="cursor-pointer text-xs text-stone-400 hover:text-stone-600">
            {unchangedRows.length} unchanged product{unchangedRows.length === 1 ? '' : 's'}
          </summary>
          <ul className="mt-1 space-y-1 text-xs text-stone-500">
            {unchangedRows.map((row) => (
              <li key={row.row_number}>{row.name_en ?? row.sku ?? `Row ${row.row_number}`}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

function ImportResultSummary({ result, onReset }: { result: CatalogImportResult; onReset: () => void }) {
  const succeeded = result.failed === 0

  return (
    <div className="space-y-3" data-testid="catalog-import-result">
      {succeeded ? (
        <p className="text-sm font-medium text-accent-700">{'✓'} Import completed successfully</p>
      ) : (
        <p className="text-sm font-medium text-stone-900">Import completed with some issues</p>
      )}

      <p className="text-sm text-stone-700">
        Created: {result.created}
        <br />
        Updated: {result.updated}
        <br />
        Unchanged: {result.unchanged}
        <br />
        Failed: {result.failed}
      </p>

      {result.failures.length > 0 && (
        <ul className="list-disc space-y-1 pl-4 text-sm text-red-600">
          {result.failures.map((failure) => (
            <li key={failure.row_number}>
              {failure.name_en ?? failure.sku ?? `Row ${failure.row_number}`}: {failure.errors.join(' ')}
            </li>
          ))}
        </ul>
      )}

      <Button variant="secondary" onClick={onReset}>
        Import Another File
      </Button>
    </div>
  )
}
