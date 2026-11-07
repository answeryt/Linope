/** An append-only journal of turns. Scheduling does not read it. */

import { AsyncLocalStorage } from 'node:async_hooks'
import fs from 'node:fs'
import path from 'node:path'

function pyJson(value: unknown): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') {
    if (Number.isNaN(value)) return 'NaN'
    if (value === Number.POSITIVE_INFINITY) return 'Infinity'
    if (value === Number.NEGATIVE_INFINITY) return '-Infinity'
    if (Number.isInteger(value)) return String(value)
    const text = JSON.stringify(value)
    return text.includes('.') || text.includes('e') || text.includes('E') ? text : `${text}.0`
  }
  if (typeof value === 'string') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(item => pyJson(item)).join(', ')}]`
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>).filter(([, item]) => item !== undefined)
    return `{${entries.map(([key, item]) => `${JSON.stringify(key)}: ${pyJson(item)}`).join(', ')}}`
  }
  throw new TypeError(`Object of type ${typeof value} is not JSON serializable`)
}

/** Python datetime.isoformat() for an aware UTC time, including real microseconds. */
export function formatUtcIso(epochMs: number): string {
  const negative = epochMs < 0
  const abs = Math.abs(epochMs)
  let wholeMs = Math.trunc(abs)
  let extraMicros = Math.round((abs - wholeMs) * 1000)
  if (extraMicros === 1000) {
    wholeMs += 1
    extraMicros = 0
  }
  let seconds = Math.trunc(wholeMs / 1000)
  let micros = (wholeMs % 1000) * 1000 + extraMicros
  if (micros >= 1_000_000) {
    seconds += 1
    micros -= 1_000_000
  }
  if (negative) seconds = -seconds
  const head = new Date(seconds * 1000).toISOString().slice(0, 19)
  if (micros === 0) return `${head}+00:00`
  return `${head}.${String(micros).padStart(6, '0')}+00:00`
}

function utcNowIso(): string {
  return formatUtcIso(performance.timeOrigin + performance.now())
}

function splitLines(text: string): string[] {
  if (!text) return []
  const parts = text.split(/\r\n|\r|\n/)
  if (parts.length > 0 && parts[parts.length - 1] === '' && /(?:\r\n|\r|\n)$/.test(text)) parts.pop()
  return parts
}

class JournalPath {
  constructor(readonly raw: string) {}

  toString(): string {
    return this.raw
  }

  get parent(): JournalPath {
    return new JournalPath(path.dirname(this.raw))
  }

  join(...parts: string[]): JournalPath {
    return new JournalPath(path.join(this.raw, ...parts))
  }

  is_file(): boolean {
    try {
      return fs.statSync(this.raw).isFile()
    } catch {
      return false
    }
  }

  read_text(): string {
    return fs.readFileSync(this.raw, 'utf8')
  }

  mkdir(): void {
    fs.mkdirSync(this.raw, { recursive: true })
  }

  append_text(data: string): void {
    fs.appendFileSync(this.raw, data, 'utf8')
  }
}

export function journal_path(folder?: string | null): JournalPath {
  const root = folder == null ? process.cwd() : folder
  return new JournalPath(root).join('.linope', 'log', 'session.jsonl')
}

export function journal_beside(ledgerPath: string): JournalPath {
  return new JournalPath(path.resolve(ledgerPath)).parent.join('log', 'session.jsonl')
}

export class Journal {
  readonly path: JournalPath

  constructor(file: string | JournalPath) {
    this.path = typeof file === 'string' ? new JournalPath(file) : file
  }

  append(event: Record<string, unknown>): void {
    this.path.parent.mkdir()
    const line = { time: utcNowIso(), ...event }
    this.path.append_text(`${pyJson(line)}\n`)
  }

  rows(): Array<Record<string, unknown>> {
    if (!this.path.is_file()) return []
    const found: Array<Record<string, unknown>> = []
    for (const raw of splitLines(this.path.read_text())) {
      if (!raw.trim()) continue
      found.push(JSON.parse(raw) as Record<string, unknown>)
    }
    return found
  }
}

type ContextFrame<T> = { value: T; parent?: ContextFrame<T>; empty?: boolean }

/** Python contextvars.ContextVar. The window and its current line use this. */
export class ContextVar<T> {
  private readonly als = new AsyncLocalStorage<ContextFrame<T>>()

  constructor(
    readonly name: string,
    private readonly fallback: T
  ) {}

  get(): T {
    const frame = this.als.getStore()
    if (!frame || frame.empty) return this.fallback
    return frame.value
  }

  set(value: T): ContextFrame<T> {
    const frame: ContextFrame<T> = { value, parent: this.als.getStore() }
    this.als.enterWith(frame)
    return frame
  }

  reset(token: ContextFrame<T>): void {
    if (this.als.getStore() !== token) {
      throw new Error(`<Token var=${this.name} was created in a different Context>`)
    }
    if (token.parent) this.als.enterWith(token.parent)
    else this.als.enterWith({ value: this.fallback, empty: true })
  }
}
