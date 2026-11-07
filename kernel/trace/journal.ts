/** An append-only journal of turns. Scheduling does not read it. */

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

function utcNowIso(): string {
  const iso = new Date().toISOString()
  const [head, rest] = iso.split('.')
  const millis = (rest || '000Z').slice(0, 3)
  return `${head}.${millis}000+00:00`
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
