/** One append-only trail of what each capability is doing. */

import fs from 'node:fs'
import path from 'node:path'

function pyJson(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : JSON.stringify(value)
  if (typeof value === 'string') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(item => pyJson(item)).join(', ')}]`
  if (typeof value === 'object') {
    return `{${Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `${JSON.stringify(key)}: ${pyJson(item)}`)
      .join(', ')}}`
  }
  throw new TypeError(`Object of type ${typeof value} is not JSON serializable`)
}

function utcNowIso(): string {
  const iso = new Date().toISOString()
  const [head, rest] = iso.split('.')
  return `${head}.${(rest || '000Z').slice(0, 3)}000+00:00`
}

function splitLines(text: string): string[] {
  if (!text) return []
  const parts = text.split(/\r\n|\r|\n/)
  if (parts.length > 0 && parts[parts.length - 1] === '' && /(?:\r\n|\r|\n)$/.test(text)) parts.pop()
  return parts
}

class ActivityPath {
  constructor(readonly raw: string) {}

  get parent(): ActivityPath {
    return new ActivityPath(path.dirname(this.raw))
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

  write_text(data: string): void {
    fs.writeFileSync(this.raw, data, 'utf8')
  }

  append_text(data: string): void {
    fs.appendFileSync(this.raw, data, 'utf8')
  }

  mkdir(): void {
    fs.mkdirSync(this.raw, { recursive: true })
  }
}

export class ActivityLog {
  readonly path: ActivityPath

  constructor(file: string) {
    this.path = new ActivityPath(file)
  }

  append(pid: number, activity: string, counterpart = '', way = ''): void {
    this.path.parent.mkdir()
    const line = {
      time: utcNowIso(),
      pid: Number(pid),
      activity,
      with: counterpart,
      way
    }
    this.path.append_text(`${pyJson(line)}\n`)
  }

  forget(pid: number): void {
    if (!this.path.is_file()) return
    const kept: string[] = []
    for (const raw of splitLines(this.path.read_text())) {
      if (!raw.trim()) continue
      const item = JSON.parse(raw) as { pid?: number }
      if (Number(item.pid || 0) === Number(pid)) continue
      kept.push(raw)
    }
    this.path.write_text(kept.length ? `${kept.join('\n')}\n` : '')
  }

  for_process(pid: number): Array<Record<string, unknown>> {
    if (!this.path.is_file()) return []
    const found: Array<Record<string, unknown>> = []
    for (const raw of splitLines(this.path.read_text())) {
      if (!raw.trim()) continue
      const item = JSON.parse(raw) as { pid?: number }
      if (Number(item.pid || 0) === Number(pid)) found.push(item as Record<string, unknown>)
    }
    return found
  }

  latest(pid: number): Record<string, unknown> | null {
    const rows = this.for_process(pid)
    if (!rows.length) return null
    return rows[rows.length - 1]
  }
}
