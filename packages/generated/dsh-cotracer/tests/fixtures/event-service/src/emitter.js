/**
 * Minimal event emitter: synchronous on/emit, used by the task processor.
 */
export class Emitter {
  constructor() {
    this.listeners = new Map()
  }

  on(name, handler) {
    const list = this.listeners.get(name) ?? []
    list.push(handler)
    this.listeners.set(name, list)
  }

  emit(name, payload) {
    for (const handler of this.listeners.get(name) ?? []) {
      handler(payload)
    }
  }
}