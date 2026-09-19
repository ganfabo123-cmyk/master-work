/**
 * Key normalization used by every cache operation. Trims whitespace,
 * lowercases, and strips a trailing slash so "user/1" and "USER/1/" are the
 * same cache key.
 */
export function normalizeKey(key) {
  return key.trim().toLowerCase().replace(/\/+$/, '')
}

/** In-memory cache whose get/set/has/delete all normalize the key first. */
export class Cache {
  constructor() {
    this.items = new Map()
  }

  set(key, value) {
    this.items.set(normalizeKey(key), value)
  }

  get(key) {
    return this.items.get(normalizeKey(key))
  }

  has(key) {
    return this.items.has(normalizeKey(key))
  }

  delete(key) {
    return this.items.delete(normalizeKey(key))
  }

  size() {
    return this.items.size
  }
}