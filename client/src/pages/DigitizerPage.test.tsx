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
    enrichDigitizerJob: vi.fn(),
    refineDigitizedProduct: vi.fn(),
    refineDigitizerJob: vi.fn(),
    detectDigitizerJobDuplicates: vi.fn(),
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
  refined_image: null,
  image_refinement_status: 'pending',
  background_isolation_status: 'not_attempted',
  duplicate_status: 'not_checked',
  duplicate_group_id: null,
  duplicate_matches: [],
  price: null,
  stock_status: 'in_stock',
  review_status: 'pending_review',
  duplicate_resolution: 'unresolved',
  reviewed_at: null,
  approved_at: null,
  merged_into_id: null,
  product_id: null,
  has_unresolved_duplicates: false,
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
  duplicate_summary: null,
}

function makeFile(name: string, type: string, sizeBytes = 1024): File {
  return new File([new Uint8Array(sizeBytes)], name, { type })
}

async function selectJob(jobId: string) {
  fireEvent.click(await screen.findByTestId(`job-history-item-${jobId}`))
}

describe('DigitizerPage', () => {
  beforeEach(() => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([])
  })

  it('renders the heading and an empty job list', async () => {
    render(<DigitizerPage />)

    expect(screen.getByText('AI Product Digitizer')).toBeInTheDocument()
    await screen.findByText('No uploads yet.')
  })

  it('selects and displays a chosen file', async () => {
    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')

    fireEvent.change(input, { target: { files: [makeFile('nuts.jpg', 'image/jpeg')] } })

    await waitFor(() => expect(screen.getByText('nuts.jpg')).toBeInTheDocument())
  })

  it('selects multiple files at once', async () => {
    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')

    fireEvent.change(input, {
      target: { files: [makeFile('a.jpg', 'image/jpeg'), makeFile('b.png', 'image/png')] },
    })

    await screen.findByText('a.jpg')
    expect(screen.getByText('b.png')).toBeInTheDocument()
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

  it('does not show an upload button until a file is selected', async () => {
    render(<DigitizerPage />)
    await screen.findByText('No uploads yet.')

    expect(screen.queryByRole('button', { name: /upload photos/i })).not.toBeInTheDocument()
  })

  it('uploads selected files and auto-selects the new job', async () => {
    vi.mocked(digitizerApi.uploadDigitizerJob).mockResolvedValue(PENDING_JOB)
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(PENDING_JOB)

    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')
    fireEvent.change(input, { target: { files: [makeFile('nuts.jpg', 'image/jpeg')] } })
    await screen.findByText('nuts.jpg')

    fireEvent.click(screen.getByRole('button', { name: /upload photos/i }))

    await waitFor(() => expect(digitizerApi.uploadDigitizerJob).toHaveBeenCalledTimes(1))
    await screen.findByTestId('job-details')
    expect(screen.queryByText('nuts.jpg')).not.toBeInTheDocument()
  })

  it('prevents duplicate submission while an upload is in progress', async () => {
    let resolveUpload!: (job: DigitizerJob) => void
    vi.mocked(digitizerApi.uploadDigitizerJob).mockReturnValue(
      new Promise<DigitizerJob>((resolve) => {
        resolveUpload = resolve
      }),
    )
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(PENDING_JOB)

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

    resolveUpload(PENDING_JOB)
  })

  it('shows an error message when upload fails and keeps the selected file', async () => {
    vi.mocked(digitizerApi.uploadDigitizerJob).mockRejectedValue(
      new digitizerApi.DigitizerApiError('Unsupported image format.', 400),
    )

    render(<DigitizerPage />)
    const input = screen.getByTestId('digitizer-file-input')
    fireEvent.change(input, { target: { files: [makeFile('nuts.jpg', 'image/jpeg')] } })
    await screen.findByText('nuts.jpg')

    fireEvent.click(screen.getByRole('button', { name: /upload photos/i }))

    expect(await screen.findByTestId('upload-error')).toHaveTextContent('Unsupported image format.')
    expect(screen.getByText('nuts.jpg')).toBeInTheDocument()
  })

  it('shows job history with a friendly status label', async () => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([PENDING_JOB])

    render(<DigitizerPage />)

    const list = await screen.findByTestId('job-history-list')
    expect(list).toHaveTextContent('1 image')
    expect(list).toHaveTextContent('Waiting')
  })

  it('does not show a job panel until a job is selected', async () => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([PENDING_JOB])

    render(<DigitizerPage />)
    await screen.findByTestId('job-history-list')

    expect(screen.queryByTestId('job-details')).not.toBeInTheDocument()
  })

  it('selecting a job shows its status and one next action', async () => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([PENDING_JOB])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(PENDING_JOB)

    render(<DigitizerPage />)
    await selectJob('job-pending-1')

    const details = await screen.findByTestId('job-details')
    expect(details).toHaveTextContent('Ready to process 1 photo')
    expect(screen.getByRole('button', { name: 'Process Photos' })).toBeInTheDocument()
  })

  it('clicking the action button processes the job', async () => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([PENDING_JOB])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(PENDING_JOB)
    let resolveProcess!: (job: DigitizerJob) => void
    vi.mocked(digitizerApi.processDigitizerJob).mockReturnValue(
      new Promise<DigitizerJob>((resolve) => {
        resolveProcess = resolve
      }),
    )

    render(<DigitizerPage />)
    await selectJob('job-pending-1')
    fireEvent.click(await screen.findByRole('button', { name: 'Process Photos' }))

    expect(digitizerApi.processDigitizerJob).toHaveBeenCalledWith('job-pending-1')
    await waitFor(() => expect(screen.getByTestId('job-details')).toHaveTextContent('Preparing products'))

    resolveProcess({ ...PENDING_JOB, status: 'completed', processed_items: 1, candidates: [] })
    await waitFor(() => expect(screen.getByTestId('job-details')).toHaveTextContent('No products found'))
  })

  it('shows a retry action and the failure reason for a failed job', async () => {
    const failedJob: DigitizerJob = {
      ...PENDING_JOB,
      status: 'failed',
      failed_items: 1,
      error_message: 'Digitization failed for all source images.',
    }
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([failedJob])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(failedJob)

    render(<DigitizerPage />)
    await selectJob('job-pending-1')

    const details = await screen.findByTestId('job-details')
    expect(details).toHaveTextContent('Needs attention')
    expect(await screen.findByTestId('job-error-message')).toHaveTextContent(
      'Digitization failed for all source images.',
    )
    expect(screen.getByRole('button', { name: 'Retry Processing' })).toBeInTheDocument()
  })

  it('shows an error if the action fails', async () => {
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([PENDING_JOB])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(PENDING_JOB)
    vi.mocked(digitizerApi.processDigitizerJob).mockRejectedValue(
      new digitizerApi.DigitizerApiError('The AI digitization service is not configured.', 503),
    )

    render(<DigitizerPage />)
    await selectJob('job-pending-1')
    fireEvent.click(await screen.findByRole('button', { name: 'Process Photos' }))

    expect(await screen.findByTestId('job-action-error')).toHaveTextContent(
      'The AI digitization service is not configured.',
    )
  })

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
    await selectJob('job-pending-1')
    return screen.findByTestId('digitized-product')
  }

  it('shows a simple product card: image and name only -- no category, no technical badges', async () => {
    const card = await renderWithCompletedJob()

    expect(card).toHaveTextContent('Almonds')
    expect(card).not.toHaveTextContent('Nuts') // category_suggestion, deliberately not shown
    expect(card).not.toHaveTextContent('92%')
    expect(card).not.toHaveTextContent('visual and text')
    expect(within(card).getByRole('img')).toBeInTheDocument()
  })

  it('never shows a "Needs review" badge -- every card on this page is unreviewed by default', async () => {
    const card = await renderWithCompletedJob()

    expect(within(card).queryByText(/needs review/i)).not.toBeInTheDocument()
  })

  it('has no separate "Details" link -- the whole card is the clickable/expandable control', async () => {
    const card = await renderWithCompletedJob()

    expect(within(card).queryByText('Details')).not.toBeInTheDocument()
    const toggle = within(card).getByTestId('toggle-product-details')
    expect(toggle.tagName).toBe('BUTTON')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    // The name and image are inside the same clickable control.
    expect(within(toggle).getByText('Almonds')).toBeInTheDocument()
    expect(within(toggle).getByRole('img')).toBeInTheDocument()
  })

  it('shows a Merged badge for a card that was merged away in Review', async () => {
    const card = await renderWithCompletedJob({ ...BASE_CANDIDATE, review_status: 'merged' })

    expect(within(card).getByText('Merged')).toBeInTheDocument()
  })

  it('reveals brand/flavor/barcode and enrich/refine actions only after opening the card', async () => {
    const card = await renderWithCompletedJob({ ...BASE_CANDIDATE, brand: 'Wehbi Roastery' })

    expect(within(card).queryByText('Wehbi Roastery')).not.toBeInTheDocument()
    expect(within(card).queryByTestId('enrich-product-button')).not.toBeInTheDocument()

    fireEvent.click(within(card).getByTestId('toggle-product-details'))

    expect(within(card).getByText('Wehbi Roastery')).toBeInTheDocument()
    expect(within(card).getByTestId('enrich-product-button')).toBeInTheDocument()
    expect(within(card).getByTestId('refine-product-button')).toBeInTheDocument()
  })

  it('the job status recommends preparing products next once detection is done', async () => {
    await renderWithCompletedJob()

    expect(screen.getByTestId('job-details')).toHaveTextContent('1 products found')
    expect(screen.getByRole('button', { name: 'Prepare Products' })).toBeInTheDocument()
  })

  it('clicking Enrich on a product card calls the enrich endpoint', async () => {
    const enriched: DigitizedProduct = { ...BASE_CANDIDATE, enrichment_status: 'enriched' }
    vi.mocked(digitizerApi.enrichDigitizedProduct).mockResolvedValue(enriched)
    const card = await renderWithCompletedJob()
    fireEvent.click(within(card).getByTestId('toggle-product-details'))

    fireEvent.click(within(card).getByTestId('enrich-product-button'))

    expect(digitizerApi.enrichDigitizedProduct).toHaveBeenCalledWith('product-1')
    await waitFor(() => expect(within(card).getByTestId('enrich-product-button')).toHaveTextContent('Re-enrich'))
  })

  it('shows an error if a single-product enrich fails', async () => {
    vi.mocked(digitizerApi.enrichDigitizedProduct).mockRejectedValue(
      new digitizerApi.DigitizerApiError('OpenRouter was unavailable.', 502),
    )
    const card = await renderWithCompletedJob()
    fireEvent.click(within(card).getByTestId('toggle-product-details'))
    fireEvent.click(within(card).getByTestId('enrich-product-button'))

    expect(await within(card).findByTestId('enrich-product-error')).toHaveTextContent(
      'OpenRouter was unavailable.',
    )
  })

  it('clicking Refine on a product card calls the refine endpoint', async () => {
    const refined: DigitizedProduct = {
      ...BASE_CANDIDATE,
      refined_image: 'refinedfile.jpg',
      image_refinement_status: 'refined',
    }
    vi.mocked(digitizerApi.refineDigitizedProduct).mockResolvedValue(refined)
    const card = await renderWithCompletedJob()
    fireEvent.click(within(card).getByTestId('toggle-product-details'))

    fireEvent.click(within(card).getByTestId('refine-product-button'))

    expect(digitizerApi.refineDigitizedProduct).toHaveBeenCalledWith('product-1')
    await waitFor(() => expect(within(card).getByTestId('refine-product-button')).toHaveTextContent('Re-refine'))
  })

  it('"Prepare Products" calls the job-level enrich endpoint', async () => {
    const completedJob: DigitizerJob = {
      ...PENDING_JOB,
      status: 'completed',
      processed_items: 1,
      candidates: [BASE_CANDIDATE],
    }
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([completedJob])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(completedJob)
    vi.mocked(digitizerApi.enrichDigitizerJob).mockResolvedValue({
      ...completedJob,
      candidates: [{ ...BASE_CANDIDATE, enrichment_status: 'enriched' }],
    })

    render(<DigitizerPage />)
    await selectJob('job-pending-1')
    fireEvent.click(await screen.findByRole('button', { name: 'Prepare Products' }))

    expect(digitizerApi.enrichDigitizerJob).toHaveBeenCalledWith('job-pending-1')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Prepare Images' })).toBeInTheDocument())
  })

  it('"Prepare Images" calls the job-level refine endpoint', async () => {
    const completedJob: DigitizerJob = {
      ...PENDING_JOB,
      status: 'completed',
      processed_items: 1,
      candidates: [{ ...BASE_CANDIDATE, enrichment_status: 'enriched' }],
    }
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([completedJob])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(completedJob)
    vi.mocked(digitizerApi.refineDigitizerJob).mockResolvedValue({
      ...completedJob,
      candidates: [{ ...completedJob.candidates[0], image_refinement_status: 'refined' }],
    })

    render(<DigitizerPage />)
    await selectJob('job-pending-1')
    fireEvent.click(await screen.findByRole('button', { name: 'Prepare Images' }))

    expect(digitizerApi.refineDigitizerJob).toHaveBeenCalledWith('job-pending-1')
  })

  it('"Check for Duplicates" calls the endpoint and flags a possible duplicate on the card', async () => {
    const readyCandidate: DigitizedProduct = {
      ...BASE_CANDIDATE,
      enrichment_status: 'enriched',
      image_refinement_status: 'refined',
    }
    const completedJob: DigitizerJob = {
      ...PENDING_JOB,
      status: 'completed',
      processed_items: 1,
      candidates: [readyCandidate],
      duplicate_summary: {
        total_candidates: 1,
        eligible_candidates: 1,
        skipped_not_enriched: 0,
        likely_count: 0,
        possible_count: 0,
        none_count: 0,
      },
    }
    vi.mocked(digitizerApi.listDigitizerJobs).mockResolvedValue([completedJob])
    vi.mocked(digitizerApi.getDigitizerJob).mockResolvedValue(completedJob)
    vi.mocked(digitizerApi.detectDigitizerJobDuplicates).mockResolvedValue({
      ...completedJob,
      candidates: [{ ...readyCandidate, duplicate_status: 'possible', has_unresolved_duplicates: true }],
    })

    render(<DigitizerPage />)
    await selectJob('job-pending-1')
    fireEvent.click(await screen.findByRole('button', { name: 'Check for Duplicates' }))

    expect(digitizerApi.detectDigitizerJobDuplicates).toHaveBeenCalledWith('job-pending-1')
    await screen.findByText('Possible duplicate')
  })

  it('does not show Merge/Keep Separate actions on the Digitizer page -- that belongs to Review', async () => {
    const flagged: DigitizedProduct = {
      ...BASE_CANDIDATE,
      duplicate_status: 'likely',
      has_unresolved_duplicates: true,
      duplicate_matches: [
        {
          matched_product_id: 'product-2',
          matched_name_en: 'Almonds',
          score: '0.95',
          reasons: ['barcode_match'],
          resolution: 'unresolved',
        },
      ],
    }
    const card = await renderWithCompletedJob(flagged)

    expect(within(card).queryByRole('button', { name: /merge/i })).not.toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: /keep separate/i })).not.toBeInTheDocument()
  })
})
