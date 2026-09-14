import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./api/digitizer', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api/digitizer')>()
  return {
    ...actual,
    listDigitizerJobs: vi.fn().mockResolvedValue([]),
    uploadDigitizerJob: vi.fn(),
  }
})

describe('App', () => {
  it('renders the project name', () => {
    render(<App />)
    expect(screen.getByText('Wehbi Nuts')).toBeInTheDocument()
  })

  it('shows the AI Product Digitizer by default', () => {
    render(<App />)
    expect(screen.getByText('AI Product Digitizer')).toBeInTheDocument()
  })
})
