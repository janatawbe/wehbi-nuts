import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as digitizerApi from '../api/digitizer'
import type { DigitizerJob } from '../types/digitizer'
import { DigitizerPage } from './DigitizerPage'

vi.mock('../api/digitizer', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/digitizer')>()
  return {
    ...actual,
    listDigitizerJobs: vi.fn(),
    uploadDigitizerJob: vi.fn(),
  }
})

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
      },
    ])

    render(<DigitizerPage />)

    expect(await screen.findByTestId('job-history-list')).toHaveTextContent('3 images')
  })

  it('shows an empty state when there is no job history', async () => {
    render(<DigitizerPage />)

    expect(await screen.findByText('No digitization jobs yet.')).toBeInTheDocument()
  })
})
