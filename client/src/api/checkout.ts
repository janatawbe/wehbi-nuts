import { API_BASE_URL } from '../config/api'
import { StorefrontApiError } from './storefront'
import type { CheckoutRequest, CheckoutResult } from '../types/checkout'

/** Submits a Cash-on-Delivery checkout. The server independently reloads
 * every product and recomputes all prices/totals from the database --
 * this request carries only product ids + requested quantity/weight, no
 * price of any kind (see types/checkout.ts and the matching backend
 * schema for why there is nothing here to trust or distrust). */
export async function submitCheckout(request: CheckoutRequest): Promise<CheckoutResult> {
  const response = await fetch(`${API_BASE_URL}/api/storefront/checkout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`
    try {
      const data: unknown = await response.json()
      if (data && typeof data === 'object' && 'detail' in data) {
        const detail = (data as { detail: unknown }).detail
        if (typeof detail === 'string') {
          message = detail
        } else if (Array.isArray(detail) && detail.length > 0) {
          // FastAPI's default 422 validation-error shape (a list of
          // {msg, loc, ...} objects) -- surface the first message rather
          // than an unreadable object dump.
          const first = detail[0]
          if (first && typeof first === 'object' && 'msg' in first && typeof first.msg === 'string') {
            message = first.msg
          }
        }
      }
    } catch {
      // Response body wasn't JSON; fall through to the generic message.
    }
    throw new StorefrontApiError(message, response.status)
  }

  return (await response.json()) as CheckoutResult
}
