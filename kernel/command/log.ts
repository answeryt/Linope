/** Print the turn journal. It is not the activity trail. */

import { guard, UsageError } from './convention.ts'
import { Journal, journal_path } from '../trace/journal.ts'

export const USAGE = 'usage: log [pid]'

function runLog(argv: string[]): number {
  if (argv.length > 1) throw new UsageError(USAGE)
  let pid: number | null = null
  if (argv.length) {
    const token = argv[0]
    if (!/^\d+$/.test(token) || Number(token) <= 0) {
      process.stderr.write('pid must be a number\n')
      return 1
    }
    pid = Number(token)
  }
  const journal = new Journal(journal_path())
  if (!journal.path.is_file()) {
    process.stderr.write('No turn log yet\n')
    return 1
  }
  let matched = 0
  for (const raw of splitLines(journal.path.read_text())) {
    if (!raw.trim()) continue
    if (pid === null) {
      process.stdout.write(`${raw}\n`)
      matched += 1
      continue
    }
    let item: { pid?: unknown }
    try {
      item = JSON.parse(raw) as { pid?: unknown }
    } catch {
      continue
    }
    if (Number(item.pid || 0) === pid) {
      process.stdout.write(`${raw}\n`)
      matched += 1
    }
  }
  if (pid !== null && matched === 0) {
    process.stderr.write(`Turn log has no such pid: ${pid}\n`)
    return 1
  }
  return 0
}

function splitLines(text: string): string[] {
  if (!text) return []
  const parts = text.split(/\r\n|\r|\n/)
  if (parts.length > 0 && parts[parts.length - 1] === '' && /(?:\r\n|\r|\n)$/.test(text)) parts.pop()
  return parts
}

export const run = guard(USAGE, runLog)
