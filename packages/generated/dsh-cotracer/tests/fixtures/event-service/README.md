# event-service (fixture)

A deliberately buggy fixture repository used to exercise CoTracer's
hypothesis-driven multi-agent debugging in a real runtime.

## Issue

Lifecycle events are never observed, even though tasks process successfully.
Run:

```sh
node src/main.js
```

Expected: `events created: 3`, `events updated: 3`, `events completed: 3`
(the processor emits one event of each kind per task, synchronously).
Actual: all three counters print `0`, while `processed results` is `3`.

## Files

- `src/emitter.js` — minimal synchronous event emitter.
- `src/processor.js` — task processor that emits `created`/`updated`/
  `completed` for each task during `process()`.
- `src/counter.js` — consumer that attaches listeners and runs the processor
  (the likely fault surface).
- `src/main.js` — reproduction script.

## Notes for the debugger

- Do not modify source files. You may write temporary probe scripts into the
  system temp directory if you need them.
- The root cause is inside this repository; a single small change fixes it.
- The emitter is synchronous: events fire inside `process()` itself, before
  it returns.