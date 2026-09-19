import { subtotal, discounted, taxOn, shippingCost, round2 } from './pricing.js'
import { discountRate } from './discounts.js'

/**
 * Checkout: given the cart items and a promo code, compute the order total.
 * The bug: shipping is decided on the PRE-discount subtotal, while free
 * shipping should apply on the DISCOUNTED amount — so an order whose
 * discounted total is below the free-shipping threshold still ships free.
 */
export function checkout(items, code) {
  const sub = subtotal(items)
  const rate = discountRate(code)
  const disc = discounted(sub, rate)
  const tax = taxOn(disc)
  // BUG: passes the pre-discount subtotal instead of the discounted amount.
  const shipping = shippingCost(sub)
  const total = round2(disc + tax + shipping)
  return { subtotal: sub, discount: round2(sub - disc), tax, shipping, total }
}