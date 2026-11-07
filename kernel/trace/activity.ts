/** One append-only trail of what each capability is doing. */

import { dumps, isRecord, loads, Path, splitLines, utcNowIso } from './journal.ts'

export class ActivityLog {
  readonly path: Path

  constructor(file: string | Path) {
    this.path = new Path(file)
  }

  append(pid: number, activity: string, counterpart = '', way = ''): void {
    this.path.parent.mkdir({ parents: true, exist_ok: true })
    const line = {
      time: utcNowIso(),
      pid: Number(pid),
      activity,
      with: counterpart,
      way
    }
    this.path.append_text(`${dumps(line)}\n`)
  }

  forget(pid: number): void {
    if (!this.path.is_file()) return
    const kept: string[] = []
    for (const raw of splitLines(this.path.read_text())) {
      if (!raw.trim()) continue
      const item = loads(raw)
      if (isRecord(item) && Number(item.pid || 0) === Number(pid)) continue
      kept.push(raw)
    }
    this.path.write_text(kept.length ? `${kept.join('\n')}\n` : '')
  }

  for_process(pid: number): Array<Record<string, unknown>> {
    if (!this.path.is_file()) return []
    const found: Array<Record<string, unknown>> = []
    for (const raw of splitLines(this.path.read_text())) {
      if (!raw.trim()) continue
      const item = loads(raw)
      if (isRecord(item) && Number(item.pid || 0) === Number(pid)) found.push(item)
    }
    return found
  }

  latest(pid: number): Record<string, unknown> | null {
    const rows = this.for_process(pid)
    if (!rows.length) return null
    return rows[rows.length - 1]
  }
}
