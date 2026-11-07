/** The address space one process may touch, managed by the scheduler. */

export const CLASSES = ['system', 'message', 'task', 'artifact'] as const

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

class PermissionError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'PermissionError'
  }
}

type KindCarrier = {
  kind?: unknown
  resource_id?: unknown
  handle?: unknown
  call_params?: unknown
  identity?: unknown
  metadata?: unknown
}

export class MemoryPointer {
  constructor(
    readonly scope: string,
    readonly resource_id: string,
    readonly classes: string[],
    readonly handle: string
  ) {}
}

export class PointerSpace {
  constructor(
    readonly pid: string,
    readonly pointers: MemoryPointer[]
  ) {}

  static from_grants(pid: unknown, grants: unknown): PointerSpace {
    const found: MemoryPointer[] = []
    for (const item of (grants as KindCarrier[]) || []) {
      if (kindOf(item) !== 'memory') continue
      const identity = identityOf(item)
      found.push(
        new MemoryPointer(
          String(identity.scope || ''),
          String(item.resource_id || ''),
          classes_of(item),
          String(item.handle || '')
        )
      )
    }
    return new PointerSpace(String(pid || ''), found)
  }

  own(): MemoryPointer | null {
    return this.pointers[0] || null
  }

  for_scope(scope: string | null | undefined): MemoryPointer | null {
    if (!scope) return this.own()
    for (const pointer of this.pointers) {
      if (pointer.scope === scope) return pointer
    }
    return null
  }

  require(className: string, scope?: string | null): MemoryPointer {
    const pointer = this.for_scope(scope)
    if (!pointer || !pointer.classes.includes(className)) {
      throw new PermissionError("This range is outside this process's address space")
    }
    return pointer
  }
}

export function classes_of(grant: KindCarrier): string[] {
  const params = grant.call_params
  let raw = ''
  if (params && typeof params === 'object' && !Array.isArray(params)) {
    raw = String((params as Record<string, unknown>).space || '')
  }
  if (!raw.trim()) return [...CLASSES]
  const names: string[] = []
  for (const part of raw.replaceAll(' ', '').split(',')) {
    if (!(CLASSES as readonly string[]).includes(part)) throw new ValueError(`Unknown memory class: ${part || raw}`)
    if (!names.includes(part)) names.push(part)
  }
  return names
}

export function authorize_resource(grants: unknown, resourceId: string): MemoryPointer {
  const wanted = String(resourceId || '')
  const space = PointerSpace.from_grants('', grants)
  for (const pointer of space.pointers) {
    if (pointer.resource_id && pointer.resource_id === wanted) return pointer
  }
  throw new PermissionError("This range is outside this process's address space")
}

export function authorize_selector(
  grants: unknown,
  selector: string
): Array<[string | null, string, number | null, number | null]> {
  const space = PointerSpace.from_grants('', grants)
  const own = space.own()
  const allowed = own ? own.classes : []
  const parsed = parse_selector(selector, allowed)
  for (const [memoryName, className] of parsed) space.require(className, memoryName)
  return parsed
}

export function parse_selector(
  selector: string,
  allowed: string[]
): Array<[string | null, string, number | null, number | null]> {
  const text = selector.trim()
  if (!text) return CLASSES.filter(name => allowed.includes(name)).map(name => [null, name, null, null])
  const parsed: Array<[string | null, string, number | null, number | null]> = []
  for (const part of text.replaceAll(',', ' ').split(/\s+/).filter(Boolean)) parsed.push(...oneTarget(part, allowed))
  return parsed
}

function oneTarget(part: string, allowed: string[]): Array<[string | null, string, number | null, number | null]> {
  const pieces = part.split('/').filter(Boolean)
  if (!pieces.length) throw new ValueError('Bad address')
  let memoryName: string | null
  let className: string
  let rest: string[]
  if ((CLASSES as readonly string[]).includes(pieces[0])) {
    memoryName = null
    className = pieces[0]
    rest = pieces.slice(1)
  } else {
    memoryName = pieces[0]
    rest = pieces.slice(1)
    if (!rest.length) return CLASSES.filter(name => allowed.includes(name)).map(name => [memoryName, name, null, null])
    className = rest[0]
    rest = rest.slice(1)
  }
  if (!(CLASSES as readonly string[]).includes(className)) throw new ValueError(`Unknown memory class: ${className}`)
  if (!allowed.includes(className)) throw new PermissionError("This range is outside this process's address space")
  if (!rest.length) return [[memoryName, className, null, null]]
  if (rest.length !== 1) throw new ValueError('Bad address')
  const [start, end] = span(rest[0])
  return [[memoryName, className, start, end]]
}

function span(raw: string): [number, number] {
  const [startText, endText] = raw.includes('-') ? raw.split('-', 2) : [raw, raw]
  if (!/^[-+]?\d+$/.test(startText) || !/^[-+]?\d+$/.test(endText)) throw new ValueError('Bad address')
  const start = Number(startText)
  const end = Number(endText)
  if (start < 0 || end < start) throw new ValueError('Bad address')
  return [start, end]
}

function kindOf(item: KindCarrier): string {
  const kind = item?.kind
  if (typeof kind === 'object' && kind !== null && 'value' in kind) return String((kind as { value: unknown }).value)
  return String(kind ?? '')
}

function identityOf(item: KindCarrier): Record<string, unknown> {
  if (item.identity && typeof item.identity === 'object' && !Array.isArray(item.identity) && Object.keys(item.identity).length) {
    return item.identity as Record<string, unknown>
  }
  const metadata = (item.metadata as Record<string, unknown> | undefined) || {}
  const nested = metadata.identity
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) return nested as Record<string, unknown>
  return {}
}
