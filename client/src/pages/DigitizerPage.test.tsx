import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as digitizerApi from '../api/digitizer'
import type { DigitizedProduct, DigitizerJob } from '../types/digitizer'
import { DigitizerPage } from './DigitizerPage'

vi.mock('../api/digitizer', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/digitizer')>()
  return {
    ...actual,
    listDigitizerJobs: vi.fn(),
    uploadDigitizerJob: vi.fn(),
    getDigitizerJob: vi.fn(),
    processDigitizerJob: vi.fn(),
    enrichDigitizedProduct: vi.fn(),
  }
})

const BASE_CANDIDATE: DigitizedProduct = {
  id: 'product-1',
  job_id: 'job-pending-1',
  source_image: 'abc123.jpg',
  crop_image: 'cropfile.jpg',
  name_en: 'Almonds',
  name_ar: 'لوز',
  category_suggestion: 'Nuts',
  category_id: null,
  presentation: 'packaged',
  ai_confidence: '0.92',
  identification_basis: 'visual_and_text',
  visible_text: 'ALMONDS 500G',
  notes: 'Slightly blurry label.',
  brand: null,
  flavor_variant: null,
  description_en: null,
  description_ar: null,
  selling_mode: null,
  package_weight: null,
  barcode: null,
  field_review: null,
  enrichment_status: 'pending',
}

const PENDING_JOB: DigitizerJob = {
  id: 'job-pending-1',
  status: 'pending',
  total_items: 1,
  processed_items: 0,
  failed_items: 0,
  error_message: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  source_images: ['abc123.jpg'],
  candidates: [],
}

function makeFile(name: string, type: string, sizeBytes = 1024): File {
  return new File([new Uint8Array(sizeBytes)], name, { type })
}

describe('DigitizerPage', () => {
  beforeEach(() => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([])
  })

  it('renders the digitizer heading and loads job history', async () => {
    render(<DigitizerPage />)

    expect(screen.getByText('AI Product Digitizer')).toBeInTheDocument()
    await waitFor(() => expect(digitizerApi.listDigitizerJobs).toHaveBeenCalledTimes(1))
  })

  it('selects and displays a chosen file', async () => {
    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')

    fireEvent.change(input, { target: { files: [makeFile('nuts.jpg', 'image/jpeg')] } })

    expect(await screen.findByText('nuts.jpg')).toBeInTheDocument()
    expect(screen.getByText('1 image selected')).toBeInTheDocument()
  })

  it('selects multiple files at once', async () => {
    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')

    fireEvent.change(input, {
      target: {
        files: [makeFile('a.jpg', 'image/jpeg'), makeFile('b.png', 'image/png')],
      },
    })

    await screen.findByText('a.jpg')
    expect(screen.getByText('b.png')).toBeInTheDocument()
    expect(screen.getByText('2 images selected')).toBeInTheDocument()
  })

  it('removes a selected file', async () => {
    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')
    fireEvent.change(input, { target: { files: [makeFile('nuts.jpg', 'image/jpeg')] } })
    await screen.findByText('nuts.jpg')

    fireEvent.click(screen.getByRole('button', { name: /remove nuts.jpg/i }))

    await waitFor(() => expect(screen.queryByText('nuts.jpg')).not.toBeInTheDocument())
  })

  it('rejects an unsupported file type client-side', async () => {
    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')

    fireEvent.change(input, { target: { files: [makeFile('doc.pdf', 'application/pdf')] } })

    expect(await screen.findByTestId('file-errors')).toHaveTextContent('unsupported file type')
    expect(screen.queryByText('doc.pdf')).not.toBeInTheDocument()
  })

  it('rejects an oversized file client-side', async () => {
    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')
    const tooBig = makeFile('huge.jpg', 'image/jpeg', 11 * 1024 * 1024)

    fireEvent.change(input, { target: { files: [tooBig] } })

    expect(await screen.findByTestId('file-errors')).toHaveTextContent('exceeds the maximum size')
    expect(screen.queryByText('huge.jpg')).not.toBeInTheDocument()
  })

  it('disables the upload button while no files are selected', () => {
    render(<DigitizerPage />)
    expect(screen.getByRole('button', { name: /upload photos/i })).toBeDisabled()
  })

  it('uploads selected files and shows a success message', async () => {
    vi.mocked(digitizerApi.uploadDigitizerJob).mockResolvedValue({
      id: 'job-11111111',
      status: 'pending',
      total_items: 1,
      processed_items: 0,
      failed_items: 0,
      error_message: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      source_images: ['abc123.jpg'],
      candidates: [],
    })

    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')
    fireEvent.change(input, { target: { files: [makeFile('nuts.jpg', 'image/jpeg')] } })
    await screen.findByText('nuts.jpg')

    fireEvent.click(screen.getByRole('button', { name: /upload photos/i }))

    expect(await screen.findByTestId('upload-success')).toHaveTextContent('Job created')
    expect(digitizerApi.uploadDigitizerJob).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('nuts.jpg')).not.toBeInTheDocument()
  })

  it('prevents duplicate submission while an upload is in progress', async () => {
    let resolveUpload!: (job: DigitizerJob) => void
    vi.mocked(digitizerApi.uploadDigitizerJob).mockReturnValue(
      new Promise<DigitizerJob>((resolve) => {
        resolveUpload = resolve
      }),
    )

    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')
    fireEvent.change(input, { target: { files: [makeFile('nuts.jpg', 'image/jpeg')] } })
    await screen.findByText('nuts.jpg')

    const button = screen.getByRole('button', { name: /upload photos/i })
    fireEvent.click(button)
    fireEvent.click(button)
    fireEvent.click(button)

    expect(await screen.findByRole('button', { name: /uploading/i })).toBeDisabled()
    expect(digitizerApi.uploadDigitizerJob).toHaveBeenCalledTimes(1)

    resolveUpload({
      id: 'job-1',
      status: 'pending',
      total_items: 1,
      processed_items: 0,
      failed_items: 0,
      error_message: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      source_images: [],
      candidates: [],
    })
  })

  it('shows an error message when upload fails', async () => {
    vi.mocked(digitizerApi.uploadDigitizerJob).mockRejectedValue(
      new digitizerApi.DigitizerApiError('Unsupported image format.', 400),
    )

    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')
    fireEvent.change(input, { target: { files: [makeFile('nuts.jpg', 'image/jpeg')] } })
    await screen.findByText('nuts.jpg')

    fireEvent.click(screen.getByRole('button', { name: /upload photos/i }))

    expect(await screen.findByTestId('upload-error')).toHaveTextContent(
      'Unsupported image format.',
    )
    // The file selection is preserved so the user can retry.
    expect(screen.getByText('nuts.jpg')).toBeInTheDocument()
  })

  it('renders recent job history', async () => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([
      {
        id: 'job-abc12345',
        status: 'pending',
        total_items: 3,
        processed_items: 0,
        failed_items: 0,
        error_message: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        source_images: [],
        candidates: [],
      },
    ])

    render(<DigitizerPage />)

    expect(await screen.findByTestId('job-history-list')).toHaveTextContent('3 images')
  })

  it('shows an empty state when there is no job history', async () => {
    render(<DigitizerPage />)

    expect(await screen.findByText('No digitization jobs yet.')).toBeInTheDocument()
  })

  // --- Milestone 4: selecting a job and processing it with AI --------

  it('shows a placeholder until a job is selected', async () => {
    render(<DigitizerPage />)

    expect(await screen.findByText('Select a job above to see its details.')).toBeInTheDocument()
  })

  it('selecting a job fetches and displays its details', async () => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([PENDING_JOB])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(PENDING_JOB)

    render(<DigitizerPage />)
    fireEvent.click(await screen.findByText('job-pend'))

    expect(await screen.findByTestId('job-details')).toHaveTextContent('Status: pending')
    expect(digitizerApi.getDigitizerJob).toHaveBeenCalledWith('job-pending-1')
  })

  it('shows a "Process with AI" button for a pending job', async () => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([PENDING_JOB])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(PENDING_JOB)

    render(<DigitizerPage />)
    fireEvent.click(await screen.findByText('job-pend'))

    expect(await screen.findByRole('button', { name: /process with ai/i })).toBeInTheDocument()
  })

  it('does not show the process button for a job already processing', async () => {
    const processingJob: DigitizerJob = { ...PENDING_JOB, status: 'processing' }
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([processingJob])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(processingJob)

    render(<DigitizerPage />)
    fireEvent.click(await screen.findByText('job-pend'))

    await screen.findByTestId('job-details')
    expect(screen.queryByRole('button', { name: /process with ai/i })).not.toBeInTheDocument()
  })

  it('clicking "Process with AI" calls the process endpoint and shows a processing state', async () => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([PENDING_JOB])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(PENDING_JOB)
    let resolveProcess!: (job: DigitizerJob) => void
    vi.mocked(digitizerApi.processDigitizerJob).mockReturnValue(
      new Promise<DigitizerJob>((resolve) => {
        resolveProcess = resolve
      }),
    )

    render(<DigitizerPage />)
    fireEvent.click(await screen.findByText('job-pend'))
    fireEvent.click(await screen.findByRole('button', { name: /process with ai/i }))

    expect(digitizerApi.processDigitizerJob).toHaveBeenCalledWith('job-pending-1')
    expect(await screen.findByTestId('job-processing')).toBeInTheDocument()

    resolveProcess({ ...PENDING_JOB, status: 'completed', processed_items: 1, candidates: [] })
    await waitFor(() => expect(screen.queryByTestId('job-processing')).not.toBeInTheDocument())
  })

  it('displays detected products with all their fields after processing completes', async () => {
    const completedJob: DigitizerJob = {
      ...PENDING_JOB,
      status: 'completed',
      processed_items: 1,
      candidates: [BASE_CANDIDATE],
    }
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([completedJob])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(completedJob)

    render(<DigitizerPage />)
    fireEvent.click(await screen.findByText('job-pend'))

    const card = await screen.findByTestId('digitized-product')
    expect(card).toHaveTextContent('Almonds')
    expect(card).toHaveTextContent('لوز')
    expect(card).toHaveTextContent('Nuts')
    expect(card).toHaveTextContent('packaged')
    expect(card).toHaveTextContent('92%')
    expect(card).toHaveTextContent('visual and text')
    expect(card).toHaveTextContent('ALMONDS 500G')
    expect(card).toHaveTextContent('Slightly blurry label.')
    const image = card.querySelector('img')
    expect(image).toHaveAttribute('src', expect.stringContaining('/media/products/cropfile.jpg'))
  })

  it('shows a clear error message for a failed job', async () => {
    const failedJob: DigitizerJob = {
      ...PENDING_JOB,
      status: 'failed',
      failed_items: 1,
      error_message: 'Digitization failed for all source images.',
    }
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([failedJob])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(failedJob)

    render(<DigitizerPage />)
    fireEvent.click(await screen.findByText('job-pend'))

    expect(await screen.findByTestId('job-error-message')).toHaveTextContent(
      'Digitization failed for all source images.',
    )
  })

  it('shows an error if processing the job fails', async () => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([PENDING_JOB])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(PENDING_JOB)
    vi.mocked(digitizerApi.processDigitizerJob).mockRejectedValue(
      new digitizerApi.DigitizerApiError('The AI digitization service is not configured.', 503),
    )

    render(<DigitizerPage />)
    fireEvent.click(await screen.findByText('job-pend'))
    fireEvent.click(await screen.findByRole('button', { name: /process with ai/i }))

    expect(await screen.findByTestId('job-process-error')).toHaveTextContent(
      'The AI digitization service is not configured.',
    )
  })

  // --- Milestone 5: enriching a single digitized product --------------

  async function renderWithCompletedJob(candidate: DigitizedProduct = BASE_CANDIDATE) {
    const completedJob: DigitizerJob = {
      ...PENDING_JOB,
      status: 'completed',
      processed_items: 1,
      candidates: [candidate],
    }
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([completedJob])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(completedJob)

    render(<DigitizerPage />)
    fireEvent.click(await screen.findByText('job-pend'))
    return screen.findByTestId('digitized-product')
  }

  it('shows an "Enrich" button on a detected product before enrichment', async () => {
    const card = await renderWithCompletedJob()

    expect(within(card).getByRole('button', { name: /^enrich$/i })).toBeInTheDocument()
  })

  it('clicking "Enrich" calls the enrich endpoint and displays the enriched fields', async () => {
    const enriched: DigitizedProduct = {
      ...BASE_CANDIDATE,
      brand: 'Wehbi Roastery',
      flavor_variant: 'Salted',
      selling_mode: 'unit',
      package_weight: '0.500',
      barcode: null,
      description_en: 'Premium roasted almonds.',
      description_ar: 'لوز محمص فاخر.',
      enrichment_status: 'enriched',
      field_review: {
        brand: { needs_review: false, reason: null },
        flavor_variant: { needs_review: false, reason: null },
        selling_mode: { needs_review: false, reason: null },
        package_weight: { needs_review: false, reason: null },
        barcode: { needs_review: false, reason: null },
        description_en: { needs_review: false, reason: null },
        description_ar: { needs_review: false, reason: null },
        category: { needs_review: false, reason: null },
      },
    }
    vi.mocked(digitizerApi.enrichDigitizedProduct).mockResolvedValue(enriched)
    const card = await renderWithCompletedJob()

    fireEvent.click(within(card).getByRole('button', { name: /^enrich$/i }))

    expect(digitizerApi.enrichDigitizedProduct).toHaveBeenCalledWith('product-1')
    expect(await within(card).findByText(/Wehbi Roastery/)).toBeInTheDocument()
    expect(within(card).getByText(/Premium roasted almonds\./)).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: /^re-enrich$/i })).toBeInTheDocument()
  })

  it('flags a field as needing review after enrichment', async () => {
    const enriched: DigitizedProduct = {
      ...BASE_CANDIDATE,
      brand: null,
      flavor_variant: null,
      selling_mode: 'weight',
      package_weight: null,
      barcode: null,
      description_en: 'Loose roasted cashews sold by weight.',
      description_ar: 'كاجو محمص يباع بالوزن.',
      enrichment_status: 'enriched',
      field_review: {
        brand: { needs_review: false, reason: null },
        flavor_variant: { needs_review: false, reason: null },
        selling_mode: { needs_review: true, reason: 'Could not tell if this is a tray or a bin.' },
        package_weight: { needs_review: false, reason: null },
        barcode: { needs_review: false, reason: null },
        description_en: { needs_review: false, reason: null },
        description_ar: { needs_review: false, reason: null },
        category: { needs_review: false, reason: null },
      },
    }
    vi.mocked(digitizerApi.enrichDigitizedProduct).mockResolvedValue(enriched)
    const card = await renderWithCompletedJob()

    fireEvent.click(within(card).getByRole('button', { name: /^enrich$/i }))

    expect(await within(card).findByText('needs review')).toBeInTheDocument()
  })

  it('shows an error if enrichment fails, without losing the enrich button', async () => {
    vi.mocked(digitizerApi.enrichDigitizedProduct).mockRejectedValue(
      new digitizerApi.DigitizerApiError('OpenRouter was unavailable.', 502),
    )
    const card = await renderWithCompletedJob()

    fireEvent.click(within(card).getByRole('button', { name: /^enrich$/i }))

    expect(await within(card).findByTestId('enrich-product-error')).toHaveTextContent(
      'OpenRouter was unavailable.',
    )
    expect(within(card).getByRole('button', { name: /^enrich$/i })).toBeInTheDocument()
  })

  it('shows a packaged item as "Per unit" with its package weight and flavor', async () => {
    const enriched: DigitizedProduct = {
      ...BASE_CANDIDATE,
      brand: 'Wehbi Roastery',
      flavor_variant: 'Salted',
      selling_mode: 'unit',
      package_weight: '0.500',
      enrichment_status: 'enriched',
      field_review: {
        brand: { needs_review: false, reason: null },
        flavor_variant: { needs_review: false, reason: null },
        selling_mode: { needs_review: false, reason: null },
        package_weight: { needs_review: false, reason: null },
        barcode: { needs_review: false, reason: null },
        description_en: { needs_review: false, reason: null },
        description_ar: { needs_review: false, reason: null },
        category: { needs_review: false, reason: null },
      },
    }
    vi.mocked(digitizerApi.enrichDigitizedProduct).mockResolvedValue(enriched)
    const card = await renderWithCompletedJob()

    fireEvent.click(within(card).getByRole('button', { name: /^enrich$/i }))

    expect(await within(card).findByText(/Per unit/)).toBeInTheDocument()
    expect(within(card).getByText(/0\.500 kg/)).toBeInTheDocument()
    expect(within(card).getByText(/Salted/)).toBeInTheDocument()
  })

  it('shows a bulk item as "By weight" with no package weight', async () => {
    const enriched: DigitizedProduct = {
      ...BASE_CANDIDATE,
      brand: null,
      flavor_variant: null,
      selling_mode: 'weight',
      package_weight: null,
      enrichment_status: 'enriched',
      field_review: {
        brand: { needs_review: false, reason: null },
        flavor_variant: { needs_review: false, reason: null },
        selling_mode: { needs_review: false, reason: null },
        package_weight: { needs_review: false, reason: null },
        barcode: { needs_review: false, reason: null },
        description_en: { needs_review: false, reason: null },
        description_ar: { needs_review: false, reason: null },
        category: { needs_review: false, reason: null },
      },
    }
    vi.mocked(digitizerApi.enrichDigitizedProduct).mockResolvedValue(enriched)
    const card = await renderWithCompletedJob()

    fireEvent.click(within(card).getByRole('button', { name: /^enrich$/i }))

    expect(await within(card).findByText(/By weight/)).toBeInTheDocument()
    expect(within(card).getByText(/None \(not packaged, or not printed\)/)).toBeInTheDocument()
  })
})
