#!/usr/bin/env node

import { createServer } from 'node:net'

const port = Number(process.argv[4])
const server = createServer()

server.listen(port, '127.0.0.1')
process.stdin.resume()
process.stdin.once('end', () => {
  server.close(() => process.exit(0))
})
