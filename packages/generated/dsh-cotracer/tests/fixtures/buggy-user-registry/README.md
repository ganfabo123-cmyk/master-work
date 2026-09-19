# buggy-user-registry (fixture)

A deliberately buggy fixture repository used to exercise CoTracer's
hypothesis-driven multi-agent debugging in a real runtime.

## Issue

After removing a user, reading the same user id still returns the user
(stale read). Reproduce with:

```sh
node src/main.js
```

Expected: `after removal, has user/1: false`.
Actual: `after removal, has user/1: true` — the removed user is still
readable and still counted.

## Files

- `src/cache.js` — key normalization + in-memory cache used by all reads.
- `src/store.js` — user registry (put/get/has/remove) over the cache.
- `src/main.js` — reproduction script.

## Notes for the debugger

- Do not modify source files. You may write temporary probe scripts into the
  system temp directory if you need them.
- The root cause is inside this repository; a single small change fixes it.