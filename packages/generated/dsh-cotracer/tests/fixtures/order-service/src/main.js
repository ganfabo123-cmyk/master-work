import { checkout } from './cart.js'

const items = [
  { name: 'Keyboard', price: 49.99, quantity: 1 },
  { name: 'Mouse', price: 29.99, quantity: 1 },
]
const code = 'SAVE15'

const order = checkout(items, code)

console.log('subtotal :', order.subtotal)   // 79.98 (>= 75, would qualify pre-discount)
console.log('discount :', order.discount)   // 12.00 (15%)
console.log('tax      :', order.tax)
console.log('shipping :', order.shipping)
console.log('total    :', order.total)