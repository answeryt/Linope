import assert from 'node:assert/strict'

import { parseKernelEvent } from './protocol.ts'

const event = parseKernelEvent(
  JSON.stringify({
    data: { capability: 'tools.read' },
    kind: 'process.started',
    pid: 7,
    seq: 1,
    version: 1
  })
)

assert.equal(event.kind, 'process.started')
assert.equal(event.pid, 7)
assert.throws(
  () => parseKernelEvent('{"version":1,"kind":"process.started","seq":1}'),
  /invalid data/
)
assert.throws(
  () => parseKernelEvent('{"version":2,"kind":"process.started","seq":1,"data":{}}'),
  /Unsupported/
)

console.log('tui protocol checks passed')
