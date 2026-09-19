import { Emitter } from './emitter.js'

const EVENTS = ['created', 'updated', 'completed']

/**
 * Task processor: emits lifecycle events synchronously as it processes each
 * task, then returns the processed task list. The emitted events fire during
 * the call itself — any listener registered only AFTER this call returns
 * will have missed every event of this batch.
 */
export class TaskProcessor {
  constructor() {
    this.emitter = new Emitter()
  }

  process(tasks) {
    const results = []
    for (const task of tasks) {
      this.emitter.emit('created', { id: task.id })
      this.emitter.emit('updated', { id: task.id, status: 'working' })
      this.emitter.emit('completed', { id: task.id })
      results.push({ id: task.id, status: 'completed' })
    }
    return results
  }

  on(name, handler) {
    this.emitter.on(name, handler)
  }
}