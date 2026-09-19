import { Cache } from './cache.js'

/**
 * User registry backed by the normalized cache. `putUser` and `getUser`
 * normalize the id through the cache's own key handling; `removeUser` is
 * the deliberate bug — deleting the raw id without the trailing-slash
 * normalization the cache applies on write, so a user stored as "user/1/"
 * can never be removed by the raw id "user/1".
 */
export class UserRegistry {
  constructor() {
    this.cache = new Cache()
  }

  putUser(user) {
    this.cache.set(user.id, user)
  }

  getUser(id) {
    return this.cache.get(id)
  }

  hasUser(id) {
    return this.cache.has(id)
  }

  removeUser(id) {
    // BUG: deletes with the raw id; the cache normalizes on set/has/get but
    // this call bypasses normalization, so a stored key that differs from the
    // raw id is never matched and the user stays cached.
    return this.cache.items.delete(id)
  }

  count() {
    return this.cache.size()
  }
}