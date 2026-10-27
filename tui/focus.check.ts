import assert from 'node:assert/strict'

import { bindingFor } from './focus.ts'
import type { Key, KeyName } from './keys.ts'

const key = (name: KeyName): Key => ({ name, raw: '', text: '' })

const inputUp = bindingFor('input', key('up'))
assert.equal(inputUp.type, 'editor')
if (inputUp.type === 'editor') {
  assert.equal(inputUp.key.name, 'up')
}

assert.deepEqual(bindingFor('history', key('up')), { type: 'scroll', delta: -1 })
assert.deepEqual(bindingFor('history', key('down')), { type: 'scroll', delta: 1 })
assert.deepEqual(bindingFor('input', key('shift-up')), { type: 'scroll', delta: -1 })
assert.deepEqual(bindingFor('history', key('shift-up')), { type: 'scroll', delta: -1 })
assert.deepEqual(bindingFor('input', key('tab')), { type: 'focus', focus: 'history' })
assert.deepEqual(bindingFor('history', key('shift-tab')), { type: 'focus', focus: 'input' })
assert.deepEqual(bindingFor('input', key('page up')), { type: 'none' })
assert.deepEqual(bindingFor('history', key('page up')), { type: 'scroll-page', direction: -1 })
assert.deepEqual(bindingFor('history', key('page down')), { type: 'scroll-page', direction: 1 })
assert.deepEqual(bindingFor('history', key('end')), { type: 'scroll-edge', edge: 'bottom' })
assert.deepEqual(bindingFor('history', key('char')), { type: 'none' })

console.log('tui focus checks passed')
