import assert from 'node:assert/strict'
import { test } from 'node:test'

import { CommandOffer, model_page } from '../page.ts'

test('a page can carry a command the agent loop chose', () => {
  const page = model_page([{ kind: 'user', content: 'hello', state: 'asked' }], {
    scope: 'chat',
    seq: 1,
    commands: [new CommandOffer('tool', 'tools.read', 8)]
  })
  assert.ok(page.links.length)
  assert.ok(page.links.some(link => link.relation === 'tool:tools.read'))
})
