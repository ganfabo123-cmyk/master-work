import { TaskProcessor } from './processor.js'

/**
 * The consumer: listens for lifecycle events and counts them. It attaches the
 * listeners AFTER process() returns, so the synchronous events fired during
 * the processing call are already gone — the counter stays at zero while the
 * processed results still report success.
 */
export class EventCounter {
  constructor(processor) {
    this.processor = processor
    this.counts = { created: 0, updated: 0, completed: 0 }
  }

  attach() {
    for (const name of Object.keys(this.counts)) {
      this.processor.on(name, () => {
        this.counts[name] += 1
      })
    }
  }

  /** Process the given tasks and report how many events were observed. */
  run(tasks) {
    const results = this.processor.process(tasks)
    this.attach()
    return { results, counts: { ...this.counts } }
  }
}