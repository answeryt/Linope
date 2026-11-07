/** Linux-style command parsing: object, subcommand, long options, and a body. */

export type Change = [string, string]

const GLOBAL: Record<string, string> = {
  'env-file': 'str',
  env: 'repeat',
  json: 'bool'
}

export class UsageError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'UsageError'
  }
}

export function env_key(raw: string): string {
  const key = raw.trim()
  if (!key || key.includes('=') || key.includes('\x00')) {
    throw new UsageError('The command names the key only; the value stays in the env file')
  }
  return key
}

export function parse_changes(raw: string[]): Change[] {
  const parsed: Change[] = []
  for (const item of raw) {
    if (!item.includes('=')) throw new UsageError('change is written as --change topic=value')
    const topic = item.split('=', 1)[0]
    const value = item.slice(topic.length + 1)
    if (!topic) throw new UsageError('change is written as --change topic=value')
    parsed.push([topic, value])
  }
  return parsed
}

export function split_body(argv: string[]): [string[], string | null] {
  if (!argv.includes('--')) return [[...argv], null]
  const index = argv.indexOf('--')
  return [argv.slice(0, index), argv.slice(index + 1).join(' ')]
}

export function parse_flags(
  argv: string[],
  flags: Record<string, string>
): [string[], Record<string, unknown>, string, string[], boolean] {
  const known: Record<string, string> = { ...GLOBAL, ...flags }
  const position: string[] = []
  const values: Record<string, unknown> = {}
  for (const [name, kind] of Object.entries(known)) {
    if (kind === 'bool') values[name] = false
    else if (kind === 'repeat') values[name] = []
    else values[name] = null
  }
  let index = 0
  while (index < argv.length) {
    const token = argv[index]
    if (token === '--' || !token.startsWith('--')) {
      position.push(token)
      index += 1
      continue
    }
    const [name, inline] = splitFlag(token)
    const kind = known[name]
    if (kind === undefined) throw new UsageError(`Unknown option: --${name}`)
    if (kind === 'bool') {
      if (inline !== null) throw new UsageError(`--${name} takes no value`)
      values[name] = true
      index += 1
      continue
    }
    let raw: string
    if (inline === null) {
      if (index + 1 >= argv.length || argv[index + 1].startsWith('--')) {
        throw new UsageError(`--${name} needs a value`)
      }
      raw = argv[index + 1]
      index += 2
    } else {
      raw = inline
      index += 1
    }
    if (kind === 'repeat') {
      const cast = values[name]
      if (Array.isArray(cast)) cast.push(raw)
      continue
    }
    values[name] = coerce(name, kind, raw)
  }
  const envFile = values['env-file']
  const envValues = values.env
  const asJson = Boolean(values.json)
  delete values['env-file']
  delete values.env
  delete values.json
  const keys = Array.isArray(envValues) ? envValues.map(item => env_key(String(item))) : []
  if (keys.length && !envFile) throw new UsageError('No env file given; cannot select keys')
  return [position, values, String(envFile || ''), keys, asJson]
}

export function require_position(position: string[], count: number, usage: string): void {
  if (position.length !== count) throw new UsageError(usage)
}

export function optional_count(raw: unknown): number | null {
  if (raw === null || raw === undefined) return null
  const number = Number(raw)
  if (!Number.isInteger(number)) throw new UsageError('--count needs an integer')
  if (number < 1) throw new UsageError('Count must be at least 1')
  return number
}

function splitFlag(token: string): [string, string | null] {
  const raw = token.slice(2)
  if (raw.includes('=')) {
    const name = raw.split('=', 1)[0]
    return [name, raw.slice(name.length + 1)]
  }
  return [raw, null]
}

function coerce(name: string, kind: string, raw: string): unknown {
  if (kind === 'int') {
    if (!/^[-+]?\d+$/.test(raw.trim())) throw new UsageError(`--${name} needs an integer`)
    return Number(raw)
  }
  if (kind === 'float') {
    if (!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?$/i.test(raw.trim())) {
      throw new UsageError(`--${name} needs a number`)
    }
    return Number(raw)
  }
  return raw
}
