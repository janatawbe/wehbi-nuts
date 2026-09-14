import { useEffect, useState } from 'react'
import {
  DigitizerApiError,
  approveDigitizedProduct,
  keepDigitizedProductsSeparate,
  mergeDigitizedProducts,
  rejectDigitizedProduct,
  updateDigitizedProductReview,
} from '../../api/digitizer'
import type {
  Category,
  DigitizedProduct,
  DigitizedProductReviewUpdate,
  SellingMode,
  StockStatus,
} from '../../types/digitizer'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { ApprovalReadiness, computeMissingRequiredFields } from './ApprovalReadiness'
import { DuplicateComparison } from './DuplicateComparison'
import { ImageComparison } from './ImageComparison'
import { isUnresolvedDuplicate } from './ReviewFilterTabs'

/** Visible marker for a field Milestone 7 approval actually requires --
 * mirrors app.services.digitizer_review_service.validate_for_approval
 * EXACTLY (English name, Arabic name, category, selling mode, price, plus
 * the image requirement shown separately near the image section). Never
 * add this to a field validate_for_approval doesn't check -- descriptions,
 * brand, flavor/variant, barcode, package_weight, and stock_status are all
 * genuinely optional for approval and must never carry this marker. */
function RequiredMark() {
  return (
    <span className="text-red-600" aria-hidden="true">
      {' '}
      *
    </span>
  )
}

interface FormState {
  name_en: string
  name_ar: string
  description_en: string
  description_ar: string
  category_id: string
  brand: string
  flavor_variant: string
  selling_mode: '' | SellingMode
  package_weight: string
  barcode: string
  price: string
  stock_status: StockStatus
}

function toFormState(product: DigitizedProduct): FormState {
  return {
    name_en: product.name_en ?? '',
    name_ar: product.name_ar ?? '',
    description_en: product.description_en ?? '',
    description_ar: product.description_ar ?? '',
    category_id: product.category_id ?? '',
    brand: product.brand ?? '',
    flavor_variant: product.flavor_variant ?? '',
    selling_mode: product.selling_mode ?? '',
    package_weight: product.package_weight ?? '',
    barcode: product.barcode ?? '',
    price: product.price ?? '',
    stock_status: product.stock_status,
  }
}

function toPayload(form: FormState): DigitizedProductReviewUpdate {
  return {
    name_en: form.name_en.trim() === '' ? null : form.name_en.trim(),
    name_ar: form.name_ar.trim() === '' ? null : form.name_ar.trim(),
    description_en: form.description_en.trim() === '' ? null : form.description_en,
    description_ar: form.description_ar.trim() === '' ? null : form.description_ar,
    category_id: form.category_id === '' ? null : form.category_id,
    brand: form.brand.trim() === '' ? null : form.brand.trim(),
    flavor_variant: form.flavor_variant.trim() === '' ? null : form.flavor_variant.trim(),
    selling_mode: form.selling_mode === '' ? null : form.selling_mode,
    package_weight: form.package_weight.trim() === '' ? null : form.package_weight.trim(),
    barcode: form.barcode.trim() === '' ? null : form.barcode.trim(),
    price: form.price.trim() === '' ? null : form.price.trim(),
    stock_status: form.stock_status,
  }
}

/** The backend joins every validate_for_approval failure reason into one
 * string, each a complete sentence ("English name is required. Category
 * is required."). Splitting it back into a list here is purely a display
 * choice (a bulleted list is easier to scan than a run-on paragraph when
 * several fields are missing) -- it never re-derives or second-guesses
 * which fields are actually required; that stays entirely backend-owned. */
function splitValidationReasons(message: string): string[] {
  return message
    .split(/(?<=\.)\s+/)
    .map((part) => part.trim())
    .filter(Boolean)
}

const INPUT_CLASSES =
  'w-full rounded-md border border-stone-300 px-3 py-2 text-sm placeholder:text-stone-400 focus:border-roast-500 focus:outline focus:outline-2 focus:outline-roast-200 disabled:bg-stone-50 disabled:text-stone-400'

interface ReviewProductDetailProps {
  product: DigitizedProduct
  allProducts: DigitizedProduct[]
  categories: Category[]
  onProductUpdated: (updated: DigitizedProduct) => void
  onNeedsFullRefresh: () => void
  onSelectProduct: (id: string) => void
}

export function ReviewProductDetail({
  product,
  allProducts,
  categories,
  onProductUpdated,
  onNeedsFullRefresh,
  onSelectProduct,
}: ReviewProductDetailProps) {
  const [form, setForm] = useState<FormState>(() => toFormState(product))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [duplicateActionError, setDuplicateActionError] = useState<string | null>(null)
  const [duplicateActionBusy, setDuplicateActionBusy] = useState<string | null>(null)

  useEffect(() => {
    setForm(toFormState(product))
    setError(null)
  }, [product])

  const isMerged = product.review_status === 'merged'
  const isApproved = product.review_status === 'approved'
  const isRejected = product.review_status === 'rejected'
  // A rejected candidate has one safe way back in -- Restore to Review --
  // and is otherwise view-only, so its fields are locked just like a
  // merged-away record's (see the action area below for what "one safe
  // way back" actually renders).
  const isLocked = isMerged || isRejected || saving
  const hasUnresolvedDuplicate = isUnresolvedDuplicate(product)

  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const save = async (): Promise<DigitizedProduct> => {
    return updateDigitizedProductReview(product.id, toPayload(form))
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const updated = await save()
      onProductUpdated(updated)
    } catch (err) {
      setError(err instanceof DigitizerApiError ? err.message : 'Could not save changes.')
    } finally {
      setSaving(false)
    }
  }

  const handleApprove = async () => {
    setSaving(true)
    setError(null)
    try {
      await save()
      const approved = await approveDigitizedProduct(product.id)
      onProductUpdated(approved)
    } catch (err) {
      setError(err instanceof DigitizerApiError ? err.message : 'Approval failed.')
    } finally {
      setSaving(false)
    }
  }

  const handleReject = async () => {
    setSaving(true)
    setError(null)
    try {
      const rejected = await rejectDigitizedProduct(product.id)
      onProductUpdated(rejected)
    } catch (err) {
      setError(err instanceof DigitizerApiError ? err.message : 'Rejection failed.')
    } finally {
      setSaving(false)
    }
  }

  const handleRestore = async () => {
    setSaving(true)
    setError(null)
    try {
      // Only the status transitions -- no other field is sent, so this
      // can never clobber an edit made elsewhere. A rejected candidate
      // never had a catalog Product (rejection requires no completeness),
      // so there is nothing to unlink or clean up here.
      const restored = await updateDigitizedProductReview(product.id, { review_status: 'draft' })
      onProductUpdated(restored)
    } catch (err) {
      setError(err instanceof DigitizerApiError ? err.message : 'Could not restore this product.')
    } finally {
      setSaving(false)
    }
  }

  const handleKeepSeparate = async (matchedId: string) => {
    setDuplicateActionBusy(matchedId)
    setDuplicateActionError(null)
    try {
      await keepDigitizedProductsSeparate([product.id, matchedId])
      onNeedsFullRefresh()
    } catch (err) {
      setDuplicateActionError(
        err instanceof DigitizerApiError ? err.message : 'Could not resolve this duplicate.',
      )
    } finally {
      setDuplicateActionBusy(null)
    }
  }

  const handleMerge = async (matchedId: string) => {
    setDuplicateActionBusy(matchedId)
    setDuplicateActionError(null)
    try {
      // The product currently open is kept as the canonical survivor; the
      // compared match is merged away. See README for this UX choice.
      await mergeDigitizedProducts(product.id, [matchedId])
      onNeedsFullRefresh()
    } catch (err) {
      setDuplicateActionError(err instanceof DigitizerApiError ? err.message : 'Merge failed.')
    } finally {
      setDuplicateActionBusy(null)
    }
  }

  const mergedIntoProduct =
    product.merged_into_id !== null ? allProducts.find((p) => p.id === product.merged_into_id) : undefined
  const missingFields = computeMissingRequiredFields(form, product)

  return (
    <div data-testid="review-detail" className="space-y-5">
      {/* The active section (Review/Duplicates/Approved/Rejected) already
          tells the reviewer the product's state -- repeating it here as a
          Draft/Approved/Rejected tag would just be noise. Only an
          exception the section itself doesn't already communicate earns a
          badge next to the name: an unresolved duplicate, or the
          merged/locked state. */}
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-stone-900">
          {product.name_en ?? '(no English name yet)'}
        </h3>
        {isMerged ? (
          <Badge tone="neutral">Merged</Badge>
        ) : (
          hasUnresolvedDuplicate && <Badge tone="warning">Possible Duplicate</Badge>
        )}
      </div>

      {isMerged && (
        <p className="text-sm text-stone-500" data-testid="merged-notice">
          Merged into {mergedIntoProduct?.name_en ?? 'another product'}.
        </p>
      )}

      <ImageComparison product={product} />

      <DuplicateComparison
        product={product}
        allProducts={allProducts}
        onMerge={handleMerge}
        onKeepSeparate={handleKeepSeparate}
        onSelectProduct={onSelectProduct}
        busyMatchId={duplicateActionBusy}
        error={duplicateActionError}
      />

      {/* --- Basic Information ------------------------------------------- */}
      <section>
        <h4 className="text-sm font-semibold uppercase tracking-wide text-stone-500">Basic Information</h4>
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block font-medium text-stone-700">
              English name
              <RequiredMark />
            </span>
            <input
              type="text"
              value={form.name_en}
              disabled={isLocked}
              aria-required="true"
              placeholder="e.g. Roasted Salted Almonds"
              onChange={(e) => updateField('name_en', e.target.value)}
              className={INPUT_CLASSES}
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium text-stone-700">
              Arabic name
              <RequiredMark />
            </span>
            <input
              type="text"
              dir="rtl"
              value={form.name_ar}
              disabled={isLocked}
              aria-required="true"
              placeholder="لوز محمص مملح"
              onChange={(e) => updateField('name_ar', e.target.value)}
              className={INPUT_CLASSES}
            />
          </label>
          <label className="text-sm sm:col-span-2">
            <span className="mb-1 block font-medium text-stone-700">
              Category
              <RequiredMark />
            </span>
            <select
              value={form.category_id}
              disabled={isLocked}
              aria-required="true"
              onChange={(e) => updateField('category_id', e.target.value)}
              className={INPUT_CLASSES}
            >
              <option value="">Select a category...</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name_en}
                </option>
              ))}
            </select>
            {categories.length === 0 && (
              <p className="mt-1 text-xs text-red-600" data-testid="no-categories-warning">
                No categories available yet.
              </p>
            )}
          </label>
        </div>
      </section>

      {/* --- Product Details -------------------------------------------- */}
      <section>
        <h4 className="text-sm font-semibold uppercase tracking-wide text-stone-500">Product Details</h4>
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="text-sm sm:col-span-2">
            <span className="mb-1 block font-medium text-stone-700">Description (EN)</span>
            <textarea
              value={form.description_en}
              disabled={isLocked}
              placeholder="Short shopper-facing description"
              onChange={(e) => updateField('description_en', e.target.value)}
              className={INPUT_CLASSES}
              rows={2}
            />
          </label>
          <label className="text-sm sm:col-span-2">
            <span className="mb-1 block font-medium text-stone-700">Description (AR)</span>
            <textarea
              dir="rtl"
              value={form.description_ar}
              disabled={isLocked}
              onChange={(e) => updateField('description_ar', e.target.value)}
              className={INPUT_CLASSES}
              rows={2}
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium text-stone-700">Brand</span>
            <input
              type="text"
              value={form.brand}
              disabled={isLocked}
              placeholder="e.g. Wehbi Nuts"
              onChange={(e) => updateField('brand', e.target.value)}
              className={INPUT_CLASSES}
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium text-stone-700">Flavor / variant</span>
            <input
              type="text"
              value={form.flavor_variant}
              disabled={isLocked}
              placeholder="e.g. Sea Salt"
              onChange={(e) => updateField('flavor_variant', e.target.value)}
              className={INPUT_CLASSES}
            />
          </label>
          <label className="text-sm sm:col-span-2">
            <span className="mb-1 block font-medium text-stone-700">Barcode</span>
            <input
              type="text"
              value={form.barcode}
              disabled={isLocked}
              placeholder="Leave blank if none is visible"
              onChange={(e) => updateField('barcode', e.target.value)}
              className={INPUT_CLASSES}
            />
          </label>
        </div>
      </section>

      {/* --- Selling ------------------------------------------------------- */}
      <section>
        <h4 className="text-sm font-semibold uppercase tracking-wide text-stone-500">Selling</h4>
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block font-medium text-stone-700">
              Selling mode
              <RequiredMark />
            </span>
            <select
              value={form.selling_mode}
              disabled={isLocked}
              aria-required="true"
              onChange={(e) => updateField('selling_mode', e.target.value as '' | SellingMode)}
              className={INPUT_CLASSES}
            >
              <option value="">Select...</option>
              <option value="unit">Unit (fixed price per package)</option>
              <option value="weight">Weight (price per kilogram)</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium text-stone-700">
              Price ({form.selling_mode === 'weight' ? 'per kg' : 'per unit'})
              <RequiredMark />
            </span>
            <input
              type="number"
              step="0.01"
              min="0"
              value={form.price}
              disabled={isLocked}
              aria-required="true"
              placeholder="0.00"
              onChange={(e) => updateField('price', e.target.value)}
              className={INPUT_CLASSES}
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium text-stone-700">
              Package weight (kg)
              {form.selling_mode === 'weight' && <span className="font-normal text-stone-400"> -- leave empty</span>}
            </span>
            <input
              type="number"
              step="0.001"
              min="0"
              value={form.package_weight}
              disabled={isLocked}
              placeholder="e.g. 0.500"
              onChange={(e) => updateField('package_weight', e.target.value)}
              className={INPUT_CLASSES}
            />
            {form.selling_mode === 'weight' && form.package_weight.trim() !== '' && (
              <p className="mt-1 text-xs text-amber-700" data-testid="package-weight-warning">
                Leave empty for weight-mode products.
              </p>
            )}
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium text-stone-700">Stock status</span>
            <select
              value={form.stock_status}
              disabled={isLocked}
              onChange={(e) => updateField('stock_status', e.target.value as StockStatus)}
              className={INPUT_CLASSES}
            >
              <option value="in_stock">In stock</option>
              <option value="low_stock">Low stock</option>
              <option value="out_of_stock">Out of stock</option>
            </select>
          </label>
        </div>
      </section>

      {!isMerged && !isRejected && <ApprovalReadiness missing={missingFields} />}

      {error && (
        <div className="text-sm text-red-600" data-testid="review-detail-error">
          {splitValidationReasons(error).length <= 1 ? (
            <p>{error}</p>
          ) : (
            <ul className="list-disc pl-4">
              {splitValidationReasons(error).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* One action area for the selected product -- its contents are
          entirely determined by review_status (+ duplicate state), never
          duplicated elsewhere (row/card/header/footer). Merged-away is
          fully locked: no action makes sense, so nothing renders here at
          all. */}
      {!isMerged && (
        <div className="flex flex-wrap items-center gap-3 border-t border-stone-100 pt-4">
          {isRejected ? (
            <Button variant="primary" disabled={saving} onClick={handleRestore}>
              Restore to Review
            </Button>
          ) : (
            <>
              <Button variant="secondary" disabled={isLocked} onClick={handleSave}>
                Save Changes
              </Button>
              {!isApproved && !hasUnresolvedDuplicate && (
                <Button variant="primary" disabled={isLocked} onClick={handleApprove}>
                  Approve
                </Button>
              )}
              {!isApproved && (
                <Button variant="danger" disabled={isLocked} onClick={handleReject}>
                  Reject
                </Button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
