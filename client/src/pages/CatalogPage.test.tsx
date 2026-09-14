import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as catalogApi from '../api/catalog'
import { CatalogApiError } from '../api/catalog'
import type { CatalogImportPreview } from '../types/catalog'
import { CatalogPage } from './CatalogPage'

vi.mock('../api/catalog', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/catalog')>()
  return {
    ...actual,
    exportCatalogXlsx: vi.fn(),
    previewCatalogImport: vi.fn(),
    confirmCatalogImport: vi.fn(),
    downloadBlob: vi.fn(),
  }
})

function makeFile(name: string, content = 'irrelevant'): File {
  return new File([content], name, {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
}

function chooseFile(file: File) {
  fireEvent.change(screen.getByTestId('catalog-import-file-input'), { target: { files: [file] } })
}

function makePreview(overrides: Partial<CatalogImportPreview> = {}): CatalogImportPreview {
  return {
    filename: 'products.xlsx',
    total_rows: 1,
    new_count: 1,
    update_count: 0,
    unchanged_count: 0,
    invalid_count: 0,
    rows: [
      {
        row_number: 2,
        action: 'new',
        product_id: null,
        sku: 'SKU-1',
        name_en: 'Almonds',
        errors: [],
        changes: [],
      },
    ],
    ...overrides,
  }
}

describe('CatalogPage', () => {
  beforeEach(() => {
    vi.mocked(catalogApi.exportCatalogXlsx).mockResolvedValue(new Blob(['x']))
  })

  it('shows a plain heading and a short description of what the page is for', () => {
    render(<CatalogPage />)

    expect(screen.getByRole('heading', { name: 'Catalog' })).toBeInTheDocument()
    expect(
      screen.getByText(
        'Manage your store products using Excel. Export your current catalog, make changes or add products, then import it back to update the store.',
      ),
    ).toBeInTheDocument()
  })

  it('shows an Export Catalog section with a plain description and only an Export Excel button', () => {
    render(<CatalogPage />)

    expect(screen.getByRole('heading', { name: 'Export Catalog' })).toBeInTheDocument()
    expect(screen.getByText('Download your current product catalog as an Excel file.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Export Excel' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /csv/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/csv/i)).not.toBeInTheDocument()
  })

  it('clicking Export Excel downloads the xlsx file', async () => {
    render(<CatalogPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Export Excel' }))

    await waitFor(() => expect(catalogApi.exportCatalogXlsx).toHaveBeenCalledTimes(1))
    expect(catalogApi.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'wehbi-nuts-catalog.xlsx')
  })

  it('shows an error message when export fails', async () => {
    vi.mocked(catalogApi.exportCatalogXlsx).mockRejectedValue(new CatalogApiError('Export failed.', 500))
    render(<CatalogPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Export Excel' }))

    expect(await screen.findByText('Export failed.')).toBeInTheDocument()
  })

  it('shows an Import Catalog section with a plain description and a Choose Excel File button', () => {
    render(<CatalogPage />)

    expect(screen.getByRole('heading', { name: 'Import Catalog' })).toBeInTheDocument()
    expect(
      screen.getByText('Upload an edited catalog or an Excel file containing new products.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Choose Excel File' })).toBeInTheDocument()
  })

  it('does not show Preview Import or a filename until a file is chosen', () => {
    render(<CatalogPage />)
    expect(screen.queryByRole('button', { name: 'Preview Import' })).not.toBeInTheDocument()
  })

  it('choosing a file shows its name and a Preview Import button', () => {
    render(<CatalogPage />)
    chooseFile(makeFile('products.xlsx'))

    expect(screen.getByText('products.xlsx')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Preview Import' })).toBeInTheDocument()
  })

  it('the file input only accepts .xlsx', () => {
    render(<CatalogPage />)
    expect(screen.getByTestId('catalog-import-file-input')).toHaveAttribute('accept', '.xlsx')
  })

  it('rejects a non-.xlsx file immediately, without calling the preview API', () => {
    render(<CatalogPage />)
    chooseFile(makeFile('products.csv'))

    expect(screen.getByTestId('catalog-import-error')).toHaveTextContent(
      'Please upload an Excel (.xlsx) file.',
    )
    expect(screen.queryByRole('button', { name: 'Preview Import' })).not.toBeInTheDocument()
    expect(catalogApi.previewCatalogImport).not.toHaveBeenCalled()
  })

  it('does not allow confirming before a preview exists', () => {
    render(<CatalogPage />)
    chooseFile(makeFile('products.xlsx'))

    expect(screen.queryByRole('button', { name: 'Confirm Import' })).not.toBeInTheDocument()
  })

  it('clicking Preview Import shows the Import Preview with New/Updates/Unchanged/Invalid counts', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockResolvedValue(
      makePreview({ new_count: 3, update_count: 8, unchanged_count: 29, invalid_count: 2, total_rows: 42 }),
    )

    render(<CatalogPage />)
    chooseFile(makeFile('products.xlsx'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))

    const preview = await screen.findByTestId('catalog-import-preview')
    expect(within(preview).getByRole('heading', { name: 'Import Preview' })).toBeInTheDocument()
    expect(preview).toHaveTextContent('3')
    expect(preview).toHaveTextContent('New')
    expect(preview).toHaveTextContent('8')
    expect(preview).toHaveTextContent('Updates')
    expect(preview).toHaveTextContent('29')
    expect(preview).toHaveTextContent('Unchanged')
    expect(preview).toHaveTextContent('2')
    expect(preview).toHaveTextContent('Invalid')
    expect(catalogApi.previewCatalogImport).toHaveBeenCalledWith(expect.any(File))
  })

  it('shows a new product with a simple "New product" label', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockResolvedValue(
      makePreview({
        rows: [
          {
            row_number: 2,
            action: 'new',
            product_id: null,
            sku: 'ALM-1',
            name_en: 'New Almond Product',
            errors: [],
            changes: [],
          },
        ],
      }),
    )

    render(<CatalogPage />)
    chooseFile(makeFile('products.xlsx'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))

    const row = await screen.findByTestId('catalog-import-row-2')
    expect(within(row).getByText('New Almond Product')).toBeInTheDocument()
    expect(within(row).getByText('New product')).toBeInTheDocument()
  })

  it('shows a clear message for an invalid product', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockResolvedValue(
      makePreview({
        invalid_count: 1,
        new_count: 0,
        rows: [
          {
            row_number: 3,
            action: 'invalid',
            product_id: null,
            sku: 'BAD-1',
            name_en: 'Pistachios',
            errors: ["Category 'Example' does not exist."],
            changes: [],
          },
        ],
      }),
    )

    render(<CatalogPage />)
    chooseFile(makeFile('products.xlsx'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))

    const row = await screen.findByTestId('catalog-import-row-3')
    expect(within(row).getByText('Pistachios')).toBeInTheDocument()
    expect(within(row).getByText("Category 'Example' does not exist.")).toBeInTheDocument()
  })

  it('shows only the meaningful field differences for an updated product', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockResolvedValue(
      makePreview({
        update_count: 1,
        new_count: 0,
        rows: [
          {
            row_number: 2,
            action: 'update',
            product_id: 'product-1',
            sku: 'SKU-1',
            name_en: 'Pistachios',
            errors: [],
            changes: [{ field: 'price', label: 'Price', old: '12.00', new: '7.00' }],
          },
        ],
      }),
    )

    render(<CatalogPage />)
    chooseFile(makeFile('products.xlsx'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))

    const row = await screen.findByTestId('catalog-import-row-2')
    expect(within(row).getByText('Pistachios')).toBeInTheDocument()
    expect(row).toHaveTextContent('Price: 12.00 → 7.00')
  })

  it('does not list unchanged products individually -- only behind a details disclosure', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockResolvedValue(
      makePreview({
        new_count: 0,
        unchanged_count: 1,
        rows: [
          {
            row_number: 2,
            action: 'unchanged',
            product_id: 'product-1',
            sku: 'SKU-1',
            name_en: 'Almonds',
            errors: [],
            changes: [],
          },
        ],
      }),
    )

    render(<CatalogPage />)
    chooseFile(makeFile('products.xlsx'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))

    const preview = await screen.findByTestId('catalog-import-preview')
    expect(screen.queryByTestId('catalog-import-row-2')).not.toBeInTheDocument()
    // Reachable only behind a collapsed disclosure, not shown as its own row.
    const disclosure = within(preview).getByText(/unchanged product/i).closest('details')
    expect(disclosure).not.toBeNull()
    expect(within(disclosure as HTMLElement).getByText('Almonds')).toBeInTheDocument()
  })

  it('shows a clear error message when the file cannot be read', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockRejectedValue(
      new CatalogApiError('Could not read the uploaded file -- make sure it is a valid .xlsx file.', 400),
    )

    render(<CatalogPage />)
    chooseFile(makeFile('bad.xlsx'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))

    expect(await screen.findByTestId('catalog-import-error')).toHaveTextContent('valid .xlsx file')
  })

  it('shows Cancel and Confirm Import together at the bottom of a successful preview', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockResolvedValue(makePreview())

    render(<CatalogPage />)
    chooseFile(makeFile('products.xlsx'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))

    await screen.findByTestId('catalog-import-preview')
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm Import' })).toBeInTheDocument()
  })

  it('clicking Confirm Import applies the changes, shows an unmistakable completion state, and hides the old form', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockResolvedValue(makePreview())
    vi.mocked(catalogApi.confirmCatalogImport).mockResolvedValue({
      created: 3,
      updated: 8,
      unchanged: 29,
      failed: 0,
      failures: [],
    })

    render(<CatalogPage />)
    const file = makeFile('products.xlsx')
    chooseFile(file)
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))
    await screen.findByTestId('catalog-import-preview')

    fireEvent.click(screen.getByRole('button', { name: 'Confirm Import' }))

    const result = await screen.findByTestId('catalog-import-result')
    expect(result).toHaveTextContent('Import completed successfully')
    expect(result).toHaveTextContent('Created: 3')
    expect(result).toHaveTextContent('Updated: 8')
    expect(result).toHaveTextContent('Unchanged: 29')
    expect(result).toHaveTextContent('Failed: 0')
    expect(catalogApi.confirmCatalogImport).toHaveBeenCalledWith(file)
    // No lingering preview table or Confirm Import button after success.
    expect(screen.queryByTestId('catalog-import-preview')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Confirm Import' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Choose Excel File' })).not.toBeInTheDocument()
  })

  it('uses different wording when the import completed with failures, instead of claiming full success', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockResolvedValue(makePreview())
    vi.mocked(catalogApi.confirmCatalogImport).mockResolvedValue({
      created: 1,
      updated: 0,
      unchanged: 0,
      failed: 1,
      failures: [{ row_number: 5, sku: 'BAD-1', name_en: 'Broken', errors: ['Price cannot be negative.'] }],
    })

    render(<CatalogPage />)
    chooseFile(makeFile('products.xlsx'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))
    await screen.findByTestId('catalog-import-preview')
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Import' }))

    const result = await screen.findByTestId('catalog-import-result')
    expect(result).not.toHaveTextContent('Import completed successfully')
    expect(result).toHaveTextContent('Failed: 1')
    expect(result).toHaveTextContent('Price cannot be negative.')
  })

  it('Import Another File resets back to the plain import form', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockResolvedValue(makePreview())
    vi.mocked(catalogApi.confirmCatalogImport).mockResolvedValue({
      created: 1,
      updated: 0,
      unchanged: 0,
      failed: 0,
      failures: [],
    })

    render(<CatalogPage />)
    chooseFile(makeFile('products.xlsx'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))
    await screen.findByTestId('catalog-import-preview')
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Import' }))
    await screen.findByTestId('catalog-import-result')

    fireEvent.click(screen.getByRole('button', { name: 'Import Another File' }))

    expect(screen.queryByTestId('catalog-import-result')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Choose Excel File' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Preview Import' })).not.toBeInTheDocument()
  })

  it('Cancel clears the selected file and preview, returning to the plain import form', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockResolvedValue(makePreview())

    render(<CatalogPage />)
    chooseFile(makeFile('products.xlsx'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))
    await screen.findByTestId('catalog-import-preview')

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByTestId('catalog-import-preview')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Preview Import' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Choose Excel File' })).toBeInTheDocument()
  })

  it('choosing a new file after a preview clears the old preview', async () => {
    vi.mocked(catalogApi.previewCatalogImport).mockResolvedValue(makePreview())

    render(<CatalogPage />)
    chooseFile(makeFile('first.xlsx'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Import' }))
    await screen.findByTestId('catalog-import-preview')

    chooseFile(makeFile('second.xlsx'))

    expect(screen.queryByTestId('catalog-import-preview')).not.toBeInTheDocument()
    expect(screen.getByText('second.xlsx')).toBeInTheDocument()
  })
})
