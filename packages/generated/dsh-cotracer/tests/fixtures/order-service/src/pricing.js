/**
 * Pricing rules: line totals, discount application, tax, and shipping.
 * Tax is applied on the discounted amount; free shipping applies when the
 * DISCOUNTED amount reaches the threshold.
 */

export const TAX_RATE = 0.07
export const FREE_SHIPPING_THRESHOLD = 75
export const SHIPPING_FEE = 9.99

/** Round a number to cents. */
export function round2(value) {
  return Math.round(value * 100) / 100
}

/** Sum of every line's price * quantity, rounded once at the end. */
export function subtotal(items) {
  return round2(items.reduce((sum, item) => sum + item.price * item.quantity, 0))
}

/** Discounted amount after applying a percentage discount. */
export function discounted(subtotal, rate) {
  return round2(subtotal * (1 - rate))
}

/** Tax on the discounted amount. */
export function taxOn(discountedAmount) {
  return round2(discountedAmount * TAX_RATE)
}

/**
 * Shipping cost for an order. Free when the discounted amount reaches the
 * threshold, otherwise a flat fee.
 */
export function shippingCost(discountedAmount) {
  if (discountedAmount >= FREE_SHIPPING_THRESHOLD) return 0
  return SHIPPING_FEE
}