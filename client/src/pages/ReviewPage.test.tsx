import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as digitizerApi from '../api/digitizer'
import { DigitizerApiError } from '../api/digitizer'
import type { Category, DigitizedProduct } from '../types/digitizer'
import { ReviewPage } from './ReviewPage'

vi.mock('../api/digitizer', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/digitizer')>()
  return {
    ...actual,
    listAllDigitizedProducts: vi.fn(),
    listCategories: vi.fn(),
    updateDigitizedProductReview: vi.fn(),
    approveDigitizedProduct: vi.fn(),
    rejectDigitizedProduct: vi.fn(),
    keepDigitizedProductsSeparate: vi.fn(),
    mergeDigitizedProducts: vi.fn(),
  }
})

function makeProduct(overrides: Partial<DigitizedProduct> = {}): DigitizedProduct {
  return {
    id: 'product-1',
    job_id: 'job-1',
    source_image: 'source1.jpg',
    crop_image: 'crop1.jpg',
    name_en: 'Roasted Almonds',
    name_ar: 'لوز',
    category_suggestion: 'Nuts',
    category_id: null,
    presentation: 'packaged',
    ai_confidence: '0.92',
    identification_basis: 'visual_and_text',
    visible_text: 'ALMONDS 500G',
    notes: null,
    brand: 'Acme',
    flavor_variant: null,
    description_en: null,
    description_ar: null,
    selling_mode: 'unit',
    package_weight: '0.500',
    barcode: null,
    field_review: null,
    enrichment_status: 'enriched',
    refined_image: 'refined1.jpg',
    image_refinement_status: 'refined',
    background_isolation_status: 'applied',
    duplicate_status: 'not_checked',
    duplicate_group_id: null,
    duplicate_matches: [],
    price: '5.00',
    stock_status: 'in_stock',
    review_status: 'pending_review',
    duplicate_resolution: 'unresolved',
    reviewed_at: null,
    approved_at: null,
    merged_into_id: null,
    product_id: null,
    has_unresolved_duplicates: false,
    ...overrides,
  }
}

const CATEGORY: Category = { id: 'cat-1', name_en: 'Nuts', name_ar: 'مكسرات', slug: 'nuts', parent_id: null }

describe('ReviewPage', () => {
  beforeEach(() => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([])
    vi.mocked(digitizerApi.listCategories).mockResolvedValue([CATEGORY])
  })

  it('renders the heading and loads products', async () => {
    render(<ReviewPage />)

    expect(screen.getByText('Review')).toBeInTheDocument()
    await waitFor(() => expect(digitizerApi.listAllDigitizedProducts).toHaveBeenCalledTimes(1))
  })

  it('shows a plain empty state when there is nothing to review yet', async () => {
    render(<ReviewPage />)

    await screen.findByText('Nothing to review yet.')
  })

  it('defaults to the Review filter and lists a pending_review product', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ review_status: 'pending_review', name_en: 'Pending Item' }),
      makeProduct({ id: 'product-2', review_status: 'approved', name_en: 'Approved Item' }),
    ])

    render(<ReviewPage />)

    expect(await screen.findByText('Pending Item')).toBeInTheDocument()
    expect(screen.queryByText('Approved Item')).not.toBeInTheDocument()
  })

  it('switches tabs to show approved products', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ review_status: 'pending_review', name_en: 'Pending Item' }),
      makeProduct({ id: 'product-2', review_status: 'approved', name_en: 'Approved Item' }),
    ])

    render(<ReviewPage />)
    await screen.findByText('Pending Item')

    fireEvent.click(screen.getByRole('tab', { name: 'Approved' }))

    expect(await screen.findByText('Approved Item')).toBeInTheDocument()
    expect(screen.queryByText('Pending Item')).not.toBeInTheDocument()
  })

  it('shows exactly four filter tabs: Review, Duplicates, Approved, Rejected', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([makeProduct()])

    render(<ReviewPage />)
    await screen.findByText('Roasted Almonds')

    expect(screen.getByRole('tab', { name: 'Review' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Duplicates' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Approved' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Rejected' })).toBeInTheDocument()
    expect(screen.getAllByRole('tab')).toHaveLength(4)
    expect(screen.queryByRole('tab', { name: 'All' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Draft' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'More' })).not.toBeInTheDocument()
  })

  it('a draft product still appears under the Review tab', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ review_status: 'draft', name_en: 'Draft Item' }),
    ])

    render(<ReviewPage />)

    expect(await screen.findByText('Draft Item')).toBeInTheDocument()
  })

  it('shows a plain empty state for a filter with no matching products', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ review_status: 'pending_review' }),
    ])

    render(<ReviewPage />)
    await screen.findByText('Roasted Almonds')
    fireEvent.click(screen.getByRole('tab', { name: 'Approved' }))

    expect(await screen.findByText('Nothing here.')).toBeInTheDocument()
  })

  it('shows a thumbnail, name, and price on each row -- no category, no extra badges', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([makeProduct()])

    render(<ReviewPage />)
    const row = await screen.findByTestId('review-row-product-1')

    expect(within(row).getByRole('img')).toBeInTheDocument()
    expect(row).toHaveTextContent('$5.00')
    expect(row).not.toHaveTextContent('Nuts')
    // The "Review" tab already means every row here needs review -- no
    // redundant badge repeating that on top.
    expect(within(row).queryByText('Needs Review')).not.toBeInTheDocument()
    expect(within(row).queryAllByText(/Enriched|Detected|Image Ready/)).toHaveLength(0)
  })

  it('shows the status badge when it is not already implied by the active tab (Duplicates mixes statuses)', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ has_unresolved_duplicates: true }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Duplicates' }))

    const row = await screen.findByTestId('review-row-product-1')
    expect(within(row).getByText('Needs Review')).toBeInTheDocument()
  })

  it('selecting a product opens the detail panel prefilled with its fields', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([makeProduct()])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))

    const detail = await screen.findByTestId('review-detail')
    expect(within(detail).getByDisplayValue('Roasted Almonds')).toBeInTheDocument()
    expect(within(detail).getByDisplayValue('Acme')).toBeInTheDocument()
    expect(within(detail).getByDisplayValue('5.00')).toBeInTheDocument()
  })

  it('does not show a Draft/Approved/Rejected tag beside the selected product name -- the active section already says so', async () => {
    const cases: Array<[Partial<DigitizedProduct>, string]> = [
      [{ review_status: 'pending_review' }, 'Review'],
      [{ review_status: 'draft' }, 'Review'],
      [{ review_status: 'approved', product_id: 'catalog-1' }, 'Approved'],
      [{ review_status: 'rejected' }, 'Rejected'],
    ]

    for (const [overrides, tab] of cases) {
      vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([makeProduct(overrides)])
      const { unmount } = render(<ReviewPage />)
      fireEvent.click(await screen.findByRole('tab', { name: tab }))
      fireEvent.click(await screen.findByText('Roasted Almonds'))
      const detail = await screen.findByTestId('review-detail')

      const header = within(detail).getByRole('heading', { name: 'Roasted Almonds' }).parentElement as HTMLElement
      expect(header).not.toHaveTextContent('Draft')
      expect(header).not.toHaveTextContent('Approved')
      expect(header).not.toHaveTextContent('Rejected')
      expect(header).not.toHaveTextContent('Needs Review')

      unmount()
    }
  })

  it('shows a Possible Duplicate badge beside the name when the product has an unresolved duplicate', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({
        has_unresolved_duplicates: true,
        duplicate_matches: [
          {
            matched_product_id: 'product-2',
            matched_name_en: 'Dup',
            score: '0.9',
            reasons: ['name_similarity'],
            resolution: 'unresolved',
          },
        ],
      }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Duplicates' }))
    fireEvent.click(await screen.findByText('Roasted Almonds', { selector: 'p' }))
    const detail = await screen.findByTestId('review-detail')

    const header = within(detail).getByRole('heading', { name: 'Roasted Almonds' }).parentElement as HTMLElement
    expect(within(header).getByText('Possible Duplicate')).toBeInTheDocument()
  })

  it('shows a Merged badge beside the name for a merged-away product', async () => {
    const survivor = makeProduct({
      id: 'product-2',
      name_en: 'Survivor',
      duplicate_matches: [
        {
          matched_product_id: 'product-1',
          matched_name_en: 'Roasted Almonds',
          score: '0.95',
          reasons: ['barcode_match'],
          resolution: 'merged',
        },
      ],
    })
    const merged = makeProduct({ review_status: 'merged', merged_into_id: 'product-2' })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([merged, survivor])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Survivor', { selector: 'p' }))
    const history = await screen.findByTestId('resolved-duplicate-history')
    fireEvent.click(within(history).getByText(/Roasted Almonds/))

    const detail = await screen.findByTestId('review-detail')
    const header = within(detail).getByRole('heading', { name: 'Roasted Almonds' }).parentElement as HTMLElement
    expect(within(header).getByText('Merged')).toBeInTheDocument()
  })

  it('shows only the final product image prominently, with originals behind a disclosure', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([makeProduct()])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')

    // The main image is outside the disclosure; the originals are inside it.
    const disclosure = within(detail).getByText('View original images').closest('details')
    expect(disclosure).not.toBeNull()
    expect(within(disclosure as HTMLElement).getByText('Original photo')).toBeInTheDocument()
    expect(within(disclosure as HTMLElement).getByText('Detected product')).toBeInTheDocument()
  })

  it('shows a refinement note when refinement failed instead of hiding the crop', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ image_refinement_status: 'failed', refined_image: null }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))

    expect(await screen.findByTestId('refinement-note')).toHaveTextContent('failed')
  })

  it('marks exactly the fields backend approval requires with a visible asterisk', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([makeProduct()])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')

    // English name, Arabic name, Category, Selling mode, Price, Product
    // Image -- exactly six, no more, no fewer.
    expect(within(detail).getAllByText('*')).toHaveLength(6)
  })

  it('shows a warning and no options when no categories exist yet', async () => {
    vi.mocked(digitizerApi.listCategories).mockResolvedValue([])
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([makeProduct()])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')

    expect(await within(detail).findByTestId('no-categories-warning')).toBeInTheDocument()
  })

  it('the category selector is populated from real backend categories', async () => {
    vi.mocked(digitizerApi.listCategories).mockResolvedValue([
      CATEGORY,
      { id: 'cat-2', name_en: 'Coffee', name_ar: 'قهوة', slug: 'coffee', parent_id: null },
    ])
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([makeProduct()])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')

    expect(within(detail).getByRole('option', { name: 'Nuts' })).toBeInTheDocument()
    expect(within(detail).getByRole('option', { name: 'Coffee' })).toBeInTheDocument()
  })

  it('shows nothing when the product is ready, and exactly what is missing otherwise', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ category_id: 'cat-1' }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')

    expect(within(detail).queryByTestId('approval-readiness')).not.toBeInTheDocument()
  })

  it('lists exactly what is still missing when the product is incomplete', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ category_id: null, price: null }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')

    const readiness = within(detail).getByTestId('approval-readiness')
    expect(readiness).toHaveTextContent('Missing:')
    expect(readiness).toHaveTextContent('Category')
    expect(readiness).toHaveTextContent('Price')
  })

  it('warns inline when package weight is filled in for a weight-mode product', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ selling_mode: 'weight', package_weight: '0.500' }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')

    expect(await within(detail).findByTestId('package-weight-warning')).toBeInTheDocument()
  })

  it('selecting a category and approving sends the chosen category_id', async () => {
    const product = makeProduct({ category_id: null })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product])
    vi.mocked(digitizerApi.updateDigitizedProductReview).mockResolvedValue({
      ...product,
      category_id: 'cat-1',
    })
    vi.mocked(digitizerApi.approveDigitizedProduct).mockResolvedValue({
      ...product,
      category_id: 'cat-1',
      review_status: 'approved',
    })

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')
    fireEvent.change(within(detail).getByRole('combobox', { name: /Category/ }), {
      target: { value: 'cat-1' },
    })
    fireEvent.click(within(detail).getByRole('button', { name: 'Approve' }))

    await waitFor(() =>
      expect(digitizerApi.updateDigitizedProductReview).toHaveBeenCalledWith(
        'product-1',
        expect.objectContaining({ category_id: 'cat-1' }),
      ),
    )
    // Once approved, the Approve/Reject actions disappear -- the active
    // "Approved" section is the only state indicator, no tag beside the name.
    await waitFor(() => expect(within(detail).queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument())
  })

  it('shows every missing required field as a clear list without losing entered data', async () => {
    const product = makeProduct({ name_en: 'Roasted Almonds', category_id: null })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product])
    vi.mocked(digitizerApi.updateDigitizedProductReview).mockResolvedValue(product)
    vi.mocked(digitizerApi.approveDigitizedProduct).mockRejectedValue(
      new DigitizerApiError('Category is required. A valid, positive price is required.', 422),
    )

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')
    const brandInput = within(detail).getByDisplayValue('Acme')
    fireEvent.change(brandInput, { target: { value: 'Still Here' } })
    fireEvent.click(within(detail).getByRole('button', { name: 'Approve' }))

    const errorBox = await within(detail).findByTestId('review-detail-error')
    expect(within(errorBox).getByText('Category is required.')).toBeInTheDocument()
    expect(within(errorBox).getByText('A valid, positive price is required.')).toBeInTheDocument()
    expect(within(detail).getByDisplayValue('Still Here')).toBeInTheDocument()
  })

  it('does not mark optional fields (description, brand, flavor, barcode, stock status) as required', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([makeProduct()])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')

    for (const label of [
      'Description (EN)',
      'Description (AR)',
      'Brand',
      'Flavor / variant',
      'Barcode',
      'Stock status',
    ]) {
      const labelElement = within(detail).getByText(label, { selector: 'span' })
      expect(labelElement.textContent).toBe(label)
    }
  })

  it('Save Changes calls the review update endpoint with the edited fields and does not approve', async () => {
    const product = makeProduct()
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product])
    vi.mocked(digitizerApi.updateDigitizedProductReview).mockResolvedValue({
      ...product,
      brand: 'New Brand',
      reviewed_at: new Date().toISOString(),
    })

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')
    const brandInput = within(detail).getByDisplayValue('Acme')
    fireEvent.change(brandInput, { target: { value: 'New Brand' } })
    fireEvent.click(within(detail).getByRole('button', { name: 'Save Changes' }))

    await waitFor(() =>
      expect(digitizerApi.updateDigitizedProductReview).toHaveBeenCalledWith(
        'product-1',
        expect.objectContaining({ brand: 'New Brand' }),
      ),
    )
    expect(digitizerApi.approveDigitizedProduct).not.toHaveBeenCalled()
    // Still not approved -- Approve/Reject remain available.
    expect(within(detail).getByRole('button', { name: 'Approve' })).toBeInTheDocument()
  })

  it('Save Changes works even when the product is incomplete', async () => {
    const product = makeProduct({ category_id: null, price: null })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product])
    vi.mocked(digitizerApi.updateDigitizedProductReview).mockResolvedValue(product)

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')
    fireEvent.click(within(detail).getByRole('button', { name: 'Save Changes' }))

    await waitFor(() => expect(digitizerApi.updateDigitizedProductReview).toHaveBeenCalledWith('product-1', expect.anything()))
    expect(within(detail).queryByTestId('review-detail-error')).not.toBeInTheDocument()
  })

  it('does not show a Save as Draft button', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([makeProduct()])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')

    expect(within(detail).queryByRole('button', { name: /save as draft/i })).not.toBeInTheDocument()
  })

  it('approve saves current edits then approves, leaving only Save Changes -- no status tag beside the name', async () => {
    const product = makeProduct()
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product])
    vi.mocked(digitizerApi.updateDigitizedProductReview).mockResolvedValue(product)
    vi.mocked(digitizerApi.approveDigitizedProduct).mockResolvedValue({
      ...product,
      review_status: 'approved',
      approved_at: new Date().toISOString(),
      product_id: 'catalog-1',
    })

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')
    fireEvent.click(within(detail).getByRole('button', { name: 'Approve' }))

    await waitFor(() => expect(digitizerApi.approveDigitizedProduct).toHaveBeenCalledWith('product-1'))
    await waitFor(() => expect(within(detail).getByRole('button', { name: 'Save Changes' })).toBeInTheDocument())
    expect(within(detail).queryByRole('button', { name: /update listing/i })).not.toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument()
    expect(within(detail).queryByText('Approved')).not.toBeInTheDocument()
  })

  it('an approved product shows only Save Changes -- no Approve or Reject', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ review_status: 'approved', product_id: 'catalog-1' }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Approved' }))
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')

    expect(within(detail).getByRole('button', { name: 'Save Changes' })).toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: /update listing/i })).not.toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument()
  })

  it('a normal unapproved product still shows Save Changes, Approve, and Reject', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([makeProduct()])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')

    expect(within(detail).getByRole('button', { name: 'Save Changes' })).toBeInTheDocument()
    expect(within(detail).getByRole('button', { name: 'Approve' })).toBeInTheDocument()
    expect(within(detail).getByRole('button', { name: 'Reject' })).toBeInTheDocument()

    // Reject reads as a full, solid destructive action -- same size,
    // padding, radius, and weight as Approve (just red instead of green),
    // not a quiet text link.
    const approveButton = within(detail).getByRole('button', { name: 'Approve' })
    const rejectButton = within(detail).getByRole('button', { name: 'Reject' })
    for (const structuralClass of ['rounded-md', 'font-medium', 'px-4', 'py-2', 'text-sm', 'shadow-sm']) {
      expect(rejectButton.className).toContain(structuralClass)
      expect(approveButton.className).toContain(structuralClass)
    }
    expect(rejectButton.className).toContain('bg-red-600')
    expect(rejectButton.className).toContain('text-white')
    expect(rejectButton.className).toContain('hover:bg-red-700')
    expect(rejectButton.className).not.toContain('underline')
    expect(rejectButton.className).not.toContain('bg-accent')
  })

  it('editing an approved product and clicking Save Changes updates the linked Product, without creating a new one', async () => {
    const product = makeProduct({ review_status: 'approved', product_id: 'catalog-1' })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product])
    vi.mocked(digitizerApi.updateDigitizedProductReview).mockResolvedValue({
      ...product,
      price: '7.50',
    })

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Approved' }))
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')
    const priceInput = within(detail).getByDisplayValue('5.00')
    fireEvent.change(priceInput, { target: { value: '7.50' } })
    fireEvent.click(within(detail).getByRole('button', { name: 'Save Changes' }))

    await waitFor(() =>
      expect(digitizerApi.updateDigitizedProductReview).toHaveBeenCalledWith(
        'product-1',
        expect.objectContaining({ price: '7.50' }),
      ),
    )
    // No separate re-approval call -- Save Changes alone keeps the catalog
    // listing synchronized, and the product's catalog linkage is untouched.
    expect(digitizerApi.approveDigitizedProduct).not.toHaveBeenCalled()
    // Still approved -- only Save Changes is shown, no Approved tag beside the name.
    expect(within(detail).getByRole('button', { name: 'Save Changes' })).toBeInTheDocument()
    expect(within(detail).queryByText('Approved')).not.toBeInTheDocument()
  })

  it('shows a clear validation message when approval fails', async () => {
    const product = makeProduct({ name_ar: null })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product])
    vi.mocked(digitizerApi.updateDigitizedProductReview).mockResolvedValue(product)
    vi.mocked(digitizerApi.approveDigitizedProduct).mockRejectedValue(
      new DigitizerApiError('Arabic name is required.', 422),
    )

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')
    fireEvent.click(within(detail).getByRole('button', { name: 'Approve' }))

    expect(await within(detail).findByTestId('review-detail-error')).toHaveTextContent(
      'Arabic name is required.',
    )
  })

  it('reject calls the reject endpoint without requiring completeness', async () => {
    const product = makeProduct({ name_ar: null, category_id: null, price: null })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product])
    vi.mocked(digitizerApi.rejectDigitizedProduct).mockResolvedValue({
      ...product,
      review_status: 'rejected',
    })

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds'))
    const detail = await screen.findByTestId('review-detail')
    fireEvent.click(within(detail).getByRole('button', { name: 'Reject' }))

    await waitFor(() => expect(digitizerApi.rejectDigitizedProduct).toHaveBeenCalledWith('product-1'))
    // Rejected view -- only Restore to Review, no "Rejected" tag beside the name.
    await waitFor(() =>
      expect(within(detail).getByRole('button', { name: 'Restore to Review' })).toBeInTheDocument(),
    )
    expect(within(detail).queryByText('Rejected')).not.toBeInTheDocument()
  })

  it('a rejected product shows only Restore to Review -- no Save Changes, Approve, or Reject', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ review_status: 'rejected' }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Rejected' }))
    fireEvent.click(await screen.findByText('Roasted Almonds', { selector: 'p' }))
    const detail = await screen.findByTestId('review-detail')

    expect(within(detail).getByRole('button', { name: 'Restore to Review' })).toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: 'Save Changes' })).not.toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument()
    // View-only: fields are locked until restored.
    expect(within(detail).getByDisplayValue('Roasted Almonds')).toBeDisabled()
  })

  it('clicking Restore to Review moves a rejected product back into Review', async () => {
    const product = makeProduct({ review_status: 'rejected' })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product])
    vi.mocked(digitizerApi.updateDigitizedProductReview).mockResolvedValue({
      ...product,
      review_status: 'draft',
    })

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Rejected' }))
    fireEvent.click(await screen.findByText('Roasted Almonds', { selector: 'p' }))
    const detail = await screen.findByTestId('review-detail')
    fireEvent.click(within(detail).getByRole('button', { name: 'Restore to Review' }))

    await waitFor(() =>
      expect(digitizerApi.updateDigitizedProductReview).toHaveBeenCalledWith('product-1', {
        review_status: 'draft',
      }),
    )

    fireEvent.click(screen.getByRole('tab', { name: 'Review' }))
    expect(await screen.findByText('Roasted Almonds', { selector: 'p' })).toBeInTheDocument()
  })

  it('shows the duplicate comparison with Keep current & merge / Keep both actions', async () => {
    const product = makeProduct({
      duplicate_status: 'likely',
      duplicate_matches: [
        {
          matched_product_id: 'product-2',
          matched_name_en: 'Roasted Almonds (dup)',
          score: '0.90',
          reasons: ['name_similarity'],
          resolution: 'unresolved',
        },
      ],
      has_unresolved_duplicates: true,
    })
    const dup = makeProduct({ id: 'product-2', name_en: 'Roasted Almonds (dup)' })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product, dup])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Duplicates' }))
    fireEvent.click(await screen.findByText('Roasted Almonds', { selector: 'p' }))

    const section = await screen.findByTestId('duplicate-section')
    expect(section).toHaveTextContent('Possible duplicate')
    expect(within(section).getByRole('button', { name: /merge duplicate/i })).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: 'Keep both' })).toBeInTheDocument()
  })

  it('cannot Approve while an unresolved duplicate relationship remains -- Save Changes and Reject still work', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({
        has_unresolved_duplicates: true,
        duplicate_matches: [
          {
            matched_product_id: 'product-2',
            matched_name_en: 'Dup',
            score: '0.9',
            reasons: ['name_similarity'],
            resolution: 'unresolved',
          },
        ],
      }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Duplicates' }))
    fireEvent.click(await screen.findByText('Roasted Almonds', { selector: 'p' }))
    const detail = await screen.findByTestId('review-detail')

    expect(await within(detail).findByTestId('duplicate-section')).toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    expect(within(detail).getByRole('button', { name: 'Save Changes' })).toBeInTheDocument()
    expect(within(detail).getByRole('button', { name: 'Reject' })).toBeInTheDocument()
  })

  it('clicking Merge merges the compared candidate into the open product', async () => {
    const product = makeProduct({
      duplicate_status: 'likely',
      duplicate_matches: [
        {
          matched_product_id: 'product-2',
          matched_name_en: 'Dup',
          score: '0.9',
          reasons: ['name_similarity'],
          resolution: 'unresolved',
        },
      ],
      has_unresolved_duplicates: true,
    })
    const dup = makeProduct({ id: 'product-2', name_en: 'Dup' })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product, dup])
    vi.mocked(digitizerApi.mergeDigitizedProducts).mockResolvedValue({
      canonical: { ...product, has_unresolved_duplicates: false },
      merged: [{ ...dup, review_status: 'merged', merged_into_id: 'product-1' }],
    })

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Duplicates' }))
    fireEvent.click(await screen.findByText('Roasted Almonds', { selector: 'p' }))
    const section = await screen.findByTestId('duplicate-section')
    fireEvent.click(within(section).getByRole('button', { name: /merge duplicate/i }))

    await waitFor(() =>
      expect(digitizerApi.mergeDigitizedProducts).toHaveBeenCalledWith('product-1', ['product-2']),
    )
    await waitFor(() => expect(digitizerApi.listAllDigitizedProducts).toHaveBeenCalledTimes(2))
  })

  it('clicking Keep both resolves the duplicate flag for both products', async () => {
    const product = makeProduct({
      duplicate_status: 'possible',
      duplicate_matches: [
        {
          matched_product_id: 'product-2',
          matched_name_en: 'Dup',
          score: '0.6',
          reasons: ['name_similarity'],
          resolution: 'unresolved',
        },
      ],
      has_unresolved_duplicates: true,
    })
    const dup = makeProduct({ id: 'product-2', name_en: 'Dup', has_unresolved_duplicates: true })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product, dup])
    vi.mocked(digitizerApi.keepDigitizedProductsSeparate).mockResolvedValue([
      { ...product, has_unresolved_duplicates: false },
      { ...dup, has_unresolved_duplicates: false },
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Duplicates' }))
    fireEvent.click(await screen.findByText('Roasted Almonds', { selector: 'p' }))
    const section = await screen.findByTestId('duplicate-section')
    fireEvent.click(within(section).getByRole('button', { name: 'Keep both' }))

    await waitFor(() =>
      expect(digitizerApi.keepDigitizedProductsSeparate).toHaveBeenCalledWith(['product-1', 'product-2']),
    )
  })

  it('resolving the only unresolved duplicate returns the product to Review and out of Duplicates', async () => {
    const product = makeProduct({
      name_en: 'Almonds A',
      has_unresolved_duplicates: true,
      duplicate_matches: [
        {
          matched_product_id: 'product-2',
          matched_name_en: 'Almonds B',
          score: '0.6',
          reasons: ['name_similarity'],
          resolution: 'unresolved',
        },
      ],
    })
    const dup = makeProduct({ id: 'product-2', name_en: 'Almonds B', has_unresolved_duplicates: true })
    const resolvedMatch = { ...product.duplicate_matches[0], resolution: 'kept_separate' as const }
    vi.mocked(digitizerApi.listAllDigitizedProducts)
      .mockResolvedValueOnce([product, dup])
      .mockResolvedValueOnce([
        { ...product, has_unresolved_duplicates: false, duplicate_matches: [resolvedMatch] },
        { ...dup, has_unresolved_duplicates: false },
      ])
    vi.mocked(digitizerApi.keepDigitizedProductsSeparate).mockResolvedValue([
      { ...product, has_unresolved_duplicates: false, duplicate_matches: [resolvedMatch] },
      { ...dup, has_unresolved_duplicates: false },
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Duplicates' }))
    fireEvent.click(await screen.findByText('Almonds A', { selector: 'p' }))
    const section = await screen.findByTestId('duplicate-section')
    fireEvent.click(within(section).getByRole('button', { name: 'Keep both' }))

    await waitFor(() => expect(digitizerApi.listAllDigitizedProducts).toHaveBeenCalledTimes(2))

    fireEvent.click(screen.getByRole('tab', { name: 'Review' }))
    expect(await screen.findByText('Almonds A', { selector: 'p' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Duplicates' }))
    expect(screen.queryByText('Almonds A', { selector: 'p' })).not.toBeInTheDocument()
  })

  it('does not show a duplicate badge once the only relationship is resolved, even though duplicate_status is stale', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({
        duplicate_status: 'possible',
        has_unresolved_duplicates: false,
        duplicate_matches: [
          {
            matched_product_id: 'product-2',
            matched_name_en: 'Dup',
            score: '0.6',
            reasons: ['name_similarity'],
            resolution: 'kept_separate',
          },
        ],
      }),
    ])

    render(<ReviewPage />)
    const row = await screen.findByTestId('review-row-product-1')

    expect(within(row).queryByText('Possible Duplicate')).not.toBeInTheDocument()
  })

  it('a product with one merged and one still-unresolved relationship still shows a warning for the unresolved one only', async () => {
    const product = makeProduct({
      duplicate_status: 'likely',
      has_unresolved_duplicates: true,
      duplicate_matches: [
        {
          matched_product_id: 'product-2',
          matched_name_en: 'Merged Away',
          score: '0.95',
          reasons: ['barcode_match'],
          resolution: 'merged',
        },
        {
          matched_product_id: 'product-3',
          matched_name_en: 'Still Pending',
          score: '0.65',
          reasons: ['name_similarity'],
          resolution: 'unresolved',
        },
      ],
    })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([product])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Duplicates' }))
    fireEvent.click(await screen.findByText('Roasted Almonds', { selector: 'p' }))

    const section = await screen.findByTestId('duplicate-section')
    expect(within(section).getByText('Still Pending')).toBeInTheDocument()
    expect(within(section).queryByText('Merged Away')).not.toBeInTheDocument()

    const history = await screen.findByTestId('resolved-duplicate-history')
    expect(within(history).getByText(/Merged Away/)).toBeInTheDocument()
  })

  it('shows resolved duplicate history without an actionable section when everything is resolved', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({
        has_unresolved_duplicates: false,
        duplicate_matches: [
          {
            matched_product_id: 'product-2',
            matched_name_en: 'Dup',
            score: '0.6',
            reasons: ['name_similarity'],
            resolution: 'kept_separate',
          },
        ],
      }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Roasted Almonds', { selector: 'p' }))

    expect(screen.queryByTestId('duplicate-section')).not.toBeInTheDocument()
    expect(await screen.findByTestId('resolved-duplicate-history')).toHaveTextContent('Kept separate')
  })

  it('the Duplicates filter only shows products with a currently unresolved relationship', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ id: 'still-unresolved', name_en: 'Still Unresolved', has_unresolved_duplicates: true }),
      makeProduct({ id: 'resolved', name_en: 'Resolved Product', has_unresolved_duplicates: false }),
      makeProduct({
        id: 'merged-away',
        name_en: 'Merged Away Product',
        review_status: 'merged',
        has_unresolved_duplicates: true,
      }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Duplicates' }))

    expect(await screen.findByText('Still Unresolved')).toBeInTheDocument()
    expect(screen.queryByText('Resolved Product')).not.toBeInTheDocument()
    expect(screen.queryByText('Merged Away Product')).not.toBeInTheDocument()
  })

  it('does not repeat "Possible Duplicate" on every row while already inside the Duplicates tab', async () => {
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([
      makeProduct({ has_unresolved_duplicates: true }),
    ])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Duplicates' }))

    const row = await screen.findByTestId('review-row-product-1')
    expect(within(row).queryByText('Possible Duplicate')).not.toBeInTheDocument()
  })

  it('a merged product is locked and view-only -- fields disabled, no action buttons at all, reached via Duplicate history', async () => {
    // Merged-away products no longer match any filter tab -- the only way
    // to reach one is by clicking its entry in the canonical survivor's
    // "Duplicate history".
    const survivor = makeProduct({
      id: 'product-2',
      name_en: 'Survivor',
      duplicate_matches: [
        {
          matched_product_id: 'product-1',
          matched_name_en: 'Roasted Almonds',
          score: '0.95',
          reasons: ['barcode_match'],
          resolution: 'merged',
        },
      ],
    })
    const merged = makeProduct({ review_status: 'merged', merged_into_id: 'product-2' })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([merged, survivor])

    render(<ReviewPage />)
    fireEvent.click(await screen.findByText('Survivor', { selector: 'p' }))
    const history = await screen.findByTestId('resolved-duplicate-history')
    fireEvent.click(within(history).getByText(/Roasted Almonds/))

    const detail = await screen.findByTestId('review-detail')
    expect(within(detail).getByTestId('merged-notice')).toBeInTheDocument()
    expect(within(detail).getByDisplayValue('Roasted Almonds')).toBeDisabled()
    expect(within(detail).queryByRole('button', { name: 'Save Changes' })).not.toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument()
    expect(within(detail).queryByRole('button', { name: /restore/i })).not.toBeInTheDocument()
  })

  it('has no selection checkboxes or bulk-action UI in any section -- clicking a row selects it directly', async () => {
    const good = makeProduct({ id: 'product-1', name_en: 'Good' })
    const bad = makeProduct({ id: 'product-2', name_en: 'Bad', review_status: 'approved', product_id: 'catalog-1' })
    vi.mocked(digitizerApi.listAllDigitizedProducts).mockResolvedValue([good, bad])

    render(<ReviewPage />)
    await screen.findByText('Good')

    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryByTestId('bulk-action-bar')).not.toBeInTheDocument()
    expect(screen.queryByText(/selected$/)).not.toBeInTheDocument()

    const goodRow = screen.getByTestId('review-row-product-1')
    fireEvent.click(within(goodRow).getByText('Good'))
    expect(await screen.findByTestId('review-detail')).toHaveTextContent('Good')
    expect(goodRow).toHaveAttribute('class', expect.stringContaining('bg-roast-50'))

    fireEvent.click(await screen.findByRole('tab', { name: 'Approved' }))
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })
})
