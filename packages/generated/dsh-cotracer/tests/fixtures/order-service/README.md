# order-service (fixture)

A deliberately buggy fixture repository used to exercise CoTracer's
hypothesis-driven multi-agent debugging in a real runtime.

## Issue

An order whose **discounted** total is below the free-shipping threshold still
gets free shipping. Run:

```sh
node src/main.js
```

The cart is Keyboard (49.99) + Mouse (29.99) with code SAVE15:
`subtotal = 79.98`, `discount = 12.00`, so the **discounted** amount is
`67.98`, which is below the 75 free-shipping threshold — shipping should be
`9.99`. Actual output shows free shipping (`0`), because the checkout decides
shipping from the pre-discount subtotal (`79.98 >= 75`).

Expected: `shipping: 9.99`. Actual: `shipping: 0`.

## Files

- `src/pricing.js` — pricing rules: subtotal, discount, tax, shipping fee.
- `src/discounts.js` — promo-code catalog.
- `src/cart.js` — checkout orchestration (the likely fault surface).
- `src/main.js` — reproduction script.

## Notes for the debugger

- Do not modify source files. You may write temporary probe scripts into the
  system temp directory if you need them.
- The root cause is inside this repository; a single small change fixes it.
- Free shipping is intended to apply when the DISCOUNTED amount reaches the
  threshold.