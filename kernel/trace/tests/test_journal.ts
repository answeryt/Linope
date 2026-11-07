import assert from 'node:assert/strict'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'

import { run } from '../../command/log.ts'
import { formatUtcIso, Journal, journal_path } from '../journal.ts'

function capture(fn: () => void): { out: string; err: string } {
  let out = ''
  let err = ''
  const stdout = process.stdout.write
  const stderr = process.stderr.write
  process.stdout.write = ((chunk: string | Uint8Array) => {
    out += String(chunk)
    return true
  }) as typeof process.stdout.write
  process.stderr.write = ((chunk: string | Uint8Array) => {
    err += String(chunk)
    return true
  }) as typeof process.stderr.write
  try {
    fn()
  } finally {
    process.stdout.write = stdout
    process.stderr.write = stderr
  }
  return { out, err }
}

test('utc timestamps use python isoformat microseconds', () => {
  const base = Date.UTC(2026, 10, 7, 14, 47, 30)
  assert.equal(formatUtcIso(base), '2026-11-07T14:47:30+00:00')
  assert.equal(formatUtcIso(base + 723.858), '2026-11-07T14:47:30.723858+00:00')
  assert.equal(formatUtcIso(base + 0.858), '2026-11-07T14:47:30.000858+00:00')
  assert.equal(formatUtcIso(base + 723), '2026-11-07T14:47:30.723000+00:00')
})

test('two appends come back in order', () => {
  const root = mkdtempSync(join(tmpdir(), 'linope-journal-'))
  const journal = new Journal(join(root, 'log', 'session.jsonl'))
  journal.append({ kind: 'line', text: 'list' })
  journal.append({ kind: 'model', pid: 7, text: 'original', step: 'read' })
  const rows = journal.rows()
  assert.deepEqual(
    rows.map(row => row.kind),
    ['line', 'model']
  )
  assert.equal(rows[0].text, 'list')
  assert.equal(rows[1].text, 'original')
  assert.equal(rows[1].pid, 7)
  assert.ok(rows[0].time)
  const again = journal.path.read_text().split(/\r\n|\n|\r/).filter(line => line !== '')
  assert.equal((JSON.parse(again[0]) as { text: string }).text, 'list')
  assert.equal((JSON.parse(again[1]) as { step: string }).step, 'read')
})

test('log prints every line and one process', () => {
  const root = mkdtempSync(join(tmpdir(), 'linope-log-'))
  const previous = process.cwd()
  process.chdir(root)
  try {
    const journal = new Journal(journal_path())
    journal.append({ kind: 'line', text: 'list' })
    journal.append({ kind: 'model', pid: 7, text: 'A', step: 'answer' })
    journal.append({ kind: 'model', pid: 8, text: 'B', step: 'read' })

    const everything = capture(() => {
      assert.equal(run([]), 0)
    })
    assert.ok(everything.out.includes('list'))
    assert.ok(everything.out.includes('A'))
    assert.ok(everything.out.includes('B'))

    const one = capture(() => {
      assert.equal(run(['7']), 0)
    })
    assert.ok(one.out.includes('A'))
    assert.equal(one.out.includes('B'), false)
    assert.equal(one.out.includes('list'), false)

    const missing = capture(() => {
      assert.equal(run(['9']), 1)
    })
    assert.ok(missing.err.includes('9'))
    const bad = capture(() => {
      assert.equal(run(['nope']), 1)
    })
    assert.ok(bad.err.includes('number'))
  } finally {
    process.chdir(previous)
  }
})

test('log without a file says so', () => {
  const root = mkdtempSync(join(tmpdir(), 'linope-log-empty-'))
  const previous = process.cwd()
  process.chdir(root)
  try {
    const captured = capture(() => {
      assert.equal(run([]), 1)
    })
    assert.ok(captured.err.includes('No turn log yet'))
  } finally {
    process.chdir(previous)
  }
})
