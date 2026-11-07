import assert from 'node:assert/strict'
import { test } from 'node:test'

import { CommandOffer, model_page } from '../../communication/page.ts'
import { memory_page, page_document } from '../memory_page.ts'
import { process_page } from '../process_page.ts'

function rows(): Array<Record<string, unknown>> {
  return [
    { address: 'system/0', kind: 'system', content: 'rules', seq: 1, time: '2026-10-22T15:00:00+00:00' },
    { address: 'message/0', kind: 'user', content: 'old question', seq: 2, time: '2026-10-22T15:01:00+00:00' },
    { address: 'message/1', kind: 'model', content: 'old answer', seq: 3, state: 'answered', time: '2026-10-22T15:02:00+00:00' },
    { address: 'message/2', kind: 'user', content: 'new question', seq: 4, state: 'asked', time: '2026-10-22T15:03:00+00:00' },
    { address: 'task/0', kind: 'other', content: 'pid=7 capability=tools.ddgs', seq: 5, state: 'resulted', time: '2026-10-22T15:04:00+00:00' }
  ]
}

test('only the named rows are shown and addresses are not linked', () => {
  const current = rows().slice(-2)
  const document = page_document(model_page(current, { scope: 's', seq: 5 }))
  assert.equal(document.state, 'resulted')
  assert.deepEqual(
    (document.rows as Array<{ content: string }>).map(row => row.content),
    ['new question', 'pid=7 capability=tools.ddgs']
  )
  const links = document._links as Record<string, unknown>
  assert.equal('message/0' in links, false)
  assert.equal('system/0' in links, false)
  assert.ok('answer' in links)
  assert.equal('time' in (links.answer as object), false)
})

test('command links carry their pointer pid and schema', () => {
  const page = model_page(rows(), {
    scope: 's',
    seq: 5,
    commands: [
      new CommandOffer('start', 'tools.firecrawl'),
      new CommandOffer('tool', 'tools.ddgs', 7, { required: ['query'] })
    ]
  })
  const links = page_document(page)._links as Record<string, Record<string, unknown>>
  assert.equal(links['start:tools.firecrawl'].pointer, 'process start tools.firecrawl')
  assert.equal(links['tool:tools.ddgs'].pointer, 'load tool 7 -- ')
  assert.equal(links['tool:tools.ddgs'].pid, 7)
  assert.deepEqual(links['tool:tools.ddgs'].schema, { required: ['query'] })
  assert.equal('time' in links['start:tools.firecrawl'], false)
  assert.equal('time' in links['tool:tools.ddgs'], false)
})

test('a handle changes when the seq changes', () => {
  const first = (page_document(model_page(rows(), { scope: 's', seq: 5 }))._links as Record<string, { handle: string }>).answer.handle
  const later = (page_document(model_page(rows(), { scope: 's', seq: 6 }))._links as Record<string, { handle: string }>).answer.handle
  assert.notEqual(first, later)
  assert.equal(first.length, 32)
})

test('a memory projection lists addresses without commands', () => {
  const document = page_document(memory_page(rows().slice(-1), { scope: 's', seq: 5 }))
  const links = document._links as Record<string, unknown>
  assert.equal('message/0' in links, false)
  assert.equal((document.rows as Array<{ content: string }>)[0].content, 'pid=7 capability=tools.ddgs')
  assert.equal('answer' in links, false)
  assert.equal('memory' in links, false)
  assert.ok(Object.keys(links).every(name => !name.startsWith('start:')))
})

test('stop is not followed with the bare pid', () => {
  const record = { pid: 4321, status: 'ready', capability_id: 'tools.ddgs', leases: [], started: 't' }
  const stop = process_page(record, 'sleeping').links.find(link => link.relation === 'stop')
  assert.ok(stop)
  assert.notEqual(stop.handle, '4321')
  assert.equal(stop.can_follow(), true)
})
