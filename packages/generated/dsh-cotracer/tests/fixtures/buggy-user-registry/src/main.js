import { UserRegistry } from './store.js'

const registry = new UserRegistry()

// Users are stored with normalized ids: a trailing slash is stripped by the
// cache's key normalization on write, so "user/1/" and "user/1" share one key.
registry.putUser({ id: 'user/1/', name: 'Alice' })
registry.putUser({ id: 'user/2', name: 'Bob' })

console.log('before removal, has "USER/1":', registry.hasUser('USER/1')) // true (has normalizes)

const removed = registry.removeUser('USER/1')
console.log('removeUser("USER/1") returned:', removed)

// Expected false after removal, but the raw-id delete never matched the
// normalized stored key ("user/1"), so the user is still cached and read
// through the normalizing get path.
console.log('after removal, has "USER/1":', registry.hasUser('USER/1'))
console.log('registry count:', registry.count())