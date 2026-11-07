import assert from 'node:assert/strict'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'

import { dumps, loads } from '../journal.ts'
import { Journal, journal_path } from '../journal.ts'
import { ActivityLog } from '../activity.ts'

test('two appends come back in order', () => {
  const root = mkdtempSync(join(tmpdir(), 'linope-journal-'))
  const journal = new Journal(join(root, 'log', 'session.jsonl'))
  journal.append({ kind: 'line', text: 'list' })
  journal.append({ kind: 'model', pid: 7, text: 'original', step: 'read' })
  const rows = journal.rows()
  assert.deepEqual(rows.map(row => row.kind), ['line', 'model'])
  assert.equal(rows[0].text, 'list')
  assert.equal(rows[1].text, 'original')
  assert.equal(rows[1].pid, 7)
  assert.ok(rows[0].time)
  const again = journal.path.read_text().split(/\n/).filter(Boolean)
  assert.equal((loads(again[0]) as { text: string }).text, 'list')
  assert.equal((loads(again[1]) as { step: string }).step, 'read')
  assert.equal(dumps({ type: 'done' }), '{"type": "done"}')
})

test('journal path sits under .linope/log', () => {
  const root = mkdtempSync(join(tmpdir(), 'linope-journal-path-'))
  assert.equal(journal_path(root).name, 'session.jsonl')
  assert.equal(journal_path(root).parent.name, 'log')
  assert.equal(journal_path(root).parent.parent.name, '.linope')
})

test('activity keeps order and forgets one pid', () => {
  const root = mkdtempSync(join(tmpdir(), 'linope-activity-'))
  const log = new ActivityLog(join(root, 'activity.jsonl'))
  log.append(4, 'self')
  log.append(4, 'with', '9', 'load')
  log.append(5, 'self')
  assert.equal(log.latest(4)?.activity, 'with')
  assert.equal(log.for_process(4).length, 2)
  log.forget(4)
  assert.equal(log.for_process(4).length, 0)
  assert.equal(log.for_process(5).length, 1)
  assert.equal(log.latest(5)?.activity, 'self')
})
