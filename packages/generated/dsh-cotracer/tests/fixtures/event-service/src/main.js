import { TaskProcessor } from './processor.js'
import { EventCounter } from './counter.js'

const processor = new TaskProcessor()
const counter = new EventCounter(processor)

const tasks = [
  { id: 't-1' },
  { id: 't-2' },
  { id: 't-3' },
]

const { results, counts } = counter.run(tasks)

console.log('processed results :', results.length)
console.log('events created    :', counts.created)
console.log('events updated    :', counts.updated)
console.log('events completed  :', counts.completed)