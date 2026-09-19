/**
 * Discount catalog: promo codes map to percentage rates.
 */
export const DISCOUNTS = {
  SAVE10: 0.10,
  SAVE15: 0.15,
  WELCOME20: 0.20,
}

/** Look up the discount rate for a promo code; unknown codes return 0. */
export function discountRate(code) {
  return DISCOUNTS[code] ?? 0
}