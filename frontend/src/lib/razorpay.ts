import { apiPost } from './http'
import type { Plan } from './plans'

/**
 * Razorpay Standard Checkout (one-time order per 30-day pass).
 *
 * The server creates the order (it owns the amount), Checkout collects UPI /
 * card / netbanking / wallet, then the server verifies the signature and
 * grants the plan. The `order.paid` webhook grants it too if this tab closes
 * before verify runs — the backend makes the two idempotent.
 */

const CHECKOUT_SRC = 'https://checkout.razorpay.com/v1/checkout.js'

interface OrderResponse {
  order_id: string
  amount: number
  currency: 'INR'
  key_id: string
  plan: Plan
  prefill: { email: string; name: string }
}

interface RazorpaySuccess {
  razorpay_order_id: string
  razorpay_payment_id: string
  razorpay_signature: string
}

interface RazorpayFailure {
  error?: { description?: string; reason?: string }
}

interface RazorpayInstance {
  open: () => void
  on: (event: 'payment.failed', cb: (resp: RazorpayFailure) => void) => void
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance
  }
}

export type CheckoutResult =
  | { status: 'paid' }
  | { status: 'dismissed' }
  | { status: 'failed'; message: string }
  /** Paid, but our verify call failed — the webhook will finish the upgrade. */
  | { status: 'pending'; message: string }

let scriptPromise: Promise<void> | null = null

function loadCheckoutScript(): Promise<void> {
  if (window.Razorpay) return Promise.resolve()
  scriptPromise ??= new Promise<void>((resolve, reject) => {
    const s = document.createElement('script')
    s.src = CHECKOUT_SRC
    s.async = true
    s.onload = () => resolve()
    s.onerror = () => {
      scriptPromise = null
      s.remove()
      reject(new Error('Could not load the payment window. Check your connection and try again.'))
    }
    document.head.appendChild(s)
  })
  return scriptPromise
}

export async function startCheckout(planId: Plan['id']): Promise<CheckoutResult> {
  const [order] = await Promise.all([
    apiPost<OrderResponse>('/billing/razorpay/order', {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_id: planId }),
    }),
    loadCheckoutScript(),
  ])
  const Razorpay = window.Razorpay
  if (!Razorpay) throw new Error('Could not load the payment window. Please try again.')

  return new Promise<CheckoutResult>((resolve) => {
    // Checkout may report a failed attempt and then let the user retry with
    // another method, so remember the last failure and settle on dismiss.
    let lastFailure: string | null = null
    let settled = false
    const settle = (r: CheckoutResult) => {
      if (!settled) {
        settled = true
        resolve(r)
      }
    }

    const rzp = new Razorpay({
      key: order.key_id,
      order_id: order.order_id,
      amount: order.amount,
      currency: order.currency,
      name: 'NorAI',
      description: `${order.plan.name} pass · ${order.plan.period_days} days`,
      prefill: { email: order.prefill.email, name: order.prefill.name },
      notes: { plan_id: planId },
      theme: { color: '#C2410C' },
      handler: async (resp: RazorpaySuccess) => {
        try {
          await apiPost('/billing/razorpay/verify', {
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(resp),
          })
          settle({ status: 'paid' })
        } catch (e) {
          settle({
            status: 'pending',
            message:
              (e instanceof Error ? e.message + ' ' : '') +
              'Your payment went through; your plan will update within a few minutes.',
          })
        }
      },
      modal: {
        ondismiss: () =>
          settle(lastFailure ? { status: 'failed', message: lastFailure } : { status: 'dismissed' }),
      },
    })
    rzp.on('payment.failed', (resp) => {
      lastFailure = resp.error?.description || 'Payment failed. No money was taken.'
    })
    rzp.open()
  })
}
