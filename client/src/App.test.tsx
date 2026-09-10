import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the project name', () => {
    render(<App />)
    expect(screen.getByText('Wehbi Nuts')).toBeInTheDocument()
  })

  it('indicates the AI Shop Digitizer and E-commerce Store features', () => {
    render(<App />)
    expect(screen.getByText('AI Shop Digitizer')).toBeInTheDocument()
    expect(screen.getByText('E-commerce Store')).toBeInTheDocument()
  })
})
