/** Fit one already-named read into the remaining context budget. */

import { spawnSync } from 'node:child_process'

import { MemoryRow } from './records.ts'
import { estimate_tokens } from './token_meter.ts'

type Fitter = (rows: MemoryRow[], budget: number) => MemoryRow[]

let fitter: Fitter | null = null

export class ContextCapacity extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ContextCapacity'
  }
}

export function register_fitter(next: Fitter | null): void {
  fitter = next
}

export function fit_named_read(rows: MemoryRow[], budget: number): [MemoryRow[], MemoryRow[]] {
  if (budget <= 0 || !rows.length) return [[], [...rows]]
  const total = rows.reduce((sum, row) => sum + (row.tokens || estimate_tokens(row.content)), 0)
  const chosen = total > budget ? advise(rows, budget) : [...rows]
  const kept: MemoryRow[] = []
  let used = 0
  for (const row of chosen) {
    const cost = row.tokens || estimate_tokens(row.content)
    if (used + cost > budget) break
    kept.push(row)
    used += cost
  }
  if (!kept.length) return [[], [...rows]]
  const keptReals = new Set(kept.map(row => row.real))
  return [kept, rows.filter(row => !keptReals.has(row.real))]
}

function advise(rows: MemoryRow[], budget: number): MemoryRow[] {
  if (!fitter) return [...rows]
  let advised: MemoryRow[]
  try {
    advised = [...fitter([...rows], budget)]
  } catch {
    return [...rows]
  }
  const known = new Map(rows.map(row => [row.real, row]))
  const found: MemoryRow[] = []
  for (const row of advised) {
    const source = known.get(row.real)
    if (!source) {
      found.push(row)
      continue
    }
    if (row.content !== source.content) {
      found.push(
        new MemoryRow(
          source.real,
          source.class_name,
          source.kind,
          row.content,
          source.time,
          source.seq,
          source.state,
          estimate_tokens(row.content),
          source.version
        )
      )
    } else found.push(source)
  }
  return found.length ? found : [...rows]
}

export function sliding_window_fit(rows: MemoryRow[], budget: number): MemoryRow[] {
  const messages = rows.map(row => ({ role: 'user', content: row.content }))
  const weights = rows.map(row => row.tokens || estimate_tokens(row.content))
  const python = process.env.LINOPE_PYTHON?.trim() || process.env.PYTHON?.trim() || 'python3'
  const completed = spawnSync(python, ['-m', 'capability.queries', 'tail-cut'], {
    input: JSON.stringify({ messages, budget: Math.max(1, budget), tokens: weights }),
    encoding: 'utf8'
  })
  let cut = 0
  if (completed.status === 0) {
    try {
      const payload = JSON.parse(String(completed.stdout || '')) as { cut?: unknown }
      const parsed = Number(payload.cut || 0)
      if (Number.isInteger(parsed)) cut = parsed
    } catch {
      cut = 0
    }
  }
  if (cut <= 0) return [...rows]
  const omitted = rows.slice(0, cut).map(row => row.real).join(', ')
  const summary = new MemoryRow(
    'summary',
    'message',
    'model',
    `Earlier rows remain stored: ${omitted}`,
    rows[0].time,
    rows[0].seq,
    '',
    estimate_tokens(omitted)
  )
  return [summary, ...rows.slice(cut)]
}
