/** One parsed command line. Objects and subcommands live in the command modules. */

import { UsageError, parse_flags, split_body } from './parser.ts'

export { UsageError }

function pyJson(value: unknown): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : JSON.stringify(value)
  if (typeof value === 'string') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(item => pyJson(item)).join(', ')}]`
  if (typeof value === 'object') {
    return `{${Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== undefined)
      .map(([key, item]) => `${JSON.stringify(key)}: ${pyJson(item)}`)
      .join(', ')}}`
  }
  return JSON.stringify(String(value))
}

export class Invocation {
  constructor(
    readonly position: string[] = [],
    readonly options: Record<string, unknown> = {},
    readonly env_file = '',
    readonly env_keys: string[] = [],
    readonly json = false,
    readonly body: string | null = null
  ) {}
}

export class Line {
  constructor(
    readonly name = '',
    readonly kind = '',
    readonly body = '',
    readonly words: string[] = [],
    readonly choice = '',
    readonly changes: Array<[string, string]> = [],
    readonly count: number | null = null,
    readonly members: string[] = [],
    readonly env_file = '',
    readonly env_keys: string[] = [],
    readonly mode = '',
    readonly operations: string[] = [],
    readonly final: string | null = null
  ) {}
}

export function parse(argv: string[], flags: Record<string, string>, usage: string): Invocation {
  void usage
  const [head, body] = split_body([...argv])
  const [position, options, envFile, envKeys, asJson] = parse_flags(head, flags)
  return new Invocation(position, options, envFile, envKeys, asJson, body)
}

export function emit(value: unknown, asJson: boolean, text?: string | null): void {
  if (asJson) {
    process.stdout.write(`${pyJson(value)}\n`)
    return
  }
  process.stdout.write(`${text == null ? String(value) : text}\n`)
}

export function guard(usage: string, fn: (argv: string[]) => number): (argv: string[]) => number {
  void usage
  return argv => {
    try {
      return fn(argv)
    } catch (error) {
      if (error instanceof UsageError || (error instanceof Error && error.name === 'UsageError')) {
        process.stderr.write(`${error.message}\n`)
        return 2
      }
      throw error
    }
  }
}
