/** Count memory tokens and peers on one network channel. */

import { spawnSync } from 'node:child_process'
import { authorize_resource, classes_of } from '../scheduler/memory_space.ts'
import { estimate_tokens } from '../resource/memory/token_meter.ts'

const IMAGE_SUFFIXES = ['.png', '.jpg', '.jpeg', '.gif', '.webp']

function pythonExecutable(): string {
  return process.env.LINOPE_PYTHON?.trim() || process.env.PYTHON?.trim() || 'python3'
}

export function resolve_default_context_length(model: string): number {
  const completed = spawnSync(pythonExecutable(), ['-m', 'capability.queries', 'context-limit', model || 'unknown/model'], {
    encoding: 'utf8'
  })
  if (completed.status !== 0) return 0
  const text = String(completed.stdout || '').trim()
  if (!/^[-+]?\d+$/.test(text)) return 0
  return Number(text)
}

export class Pressure {
  constructor(
    readonly tokens: number,
    readonly context_limit: number,
    readonly context_full: boolean,
    readonly channel: string,
    readonly peers: number,
    readonly activity: string
  ) {}
}

export function count_tokens(model: string, content: unknown): number {
  const name = model || 'gpt-4o'
  if (isImage(content)) {
    const url = typeof content === 'string' ? content : String((content as { url?: unknown }).url || '')
    return counter(name, {
      messages: [{ role: 'user', content: [{ type: 'image_url', image_url: { url } }] }],
      use_default_image_token_count: true
    })
  }
  const text = typeof content === 'string' ? content : ''
  if (!text) return 0
  return counter(name, { text })
}

export function measure(options: {
  pool: unknown
  record: { leases?: unknown; pid?: unknown }
  book: { records: () => Array<{ pid: unknown; status: unknown; leases?: unknown }> } | null
  activity: string
  model?: string
}): Pressure {
  const leases = [...((options.record.leases as unknown[]) || [])]
  const name = String(options.model || '')
  const tokens = estimate_tokens(memorySystem(options.pool, leases))
  const limit = resolve_default_context_length(name || 'unknown/model')
  const channel = channelOf(leases)
  return new Pressure(
    tokens,
    limit,
    limit > 0 && tokens >= limit,
    channel,
    peers(options.book, options.record, channel),
    String(options.activity || 'sleeping')
  )
}

function memorySystem(pool: unknown, grants: unknown): string {
  const list = [...((grants as object[]) || [])]
  const grant = list.find(item => kindOf(item) === 'memory') as { resource_id?: unknown; call_params?: unknown } | undefined
  if (!grant || pool == null) return ''
  if (!classes_of(grant).includes('system')) return ''
  authorize_resource(list, String(grant.resource_id || ''))
  const store = (pool as { store?: { entity?: (id: string) => { resource_id?: unknown } | null; memory?: { system_text: (id: string) => string } } }).store
  const entity = store?.entity?.(String(grant.resource_id || ''))
  const resourceId = entity?.resource_id
  if (!entity || !resourceId) return ''
  return String(store?.memory?.system_text(String(resourceId)) || '')
}

function kindOf(item: unknown): string {
  const kind = (item as { kind?: unknown })?.kind
  if (typeof kind === 'object' && kind !== null && 'value' in kind) return String((kind as { value: unknown }).value)
  return String(kind ?? '')
}

function counter(model: string, payload: Record<string, unknown>): number {
  const script = `
import json, sys, litellm
payload = json.loads(sys.stdin.read())
model = payload.pop("model")
try:
    print(int(litellm.token_counter(model=model, **payload)))
except Exception:
    print(int(litellm.token_counter(model="gpt-4o", **payload)))
`
  const completed = spawnSync(pythonExecutable(), ['-c', script], {
    input: JSON.stringify({ model, ...payload }),
    encoding: 'utf8'
  })
  const text = String(completed.stdout || '').trim()
  if (completed.status !== 0 || !/^[-+]?\d+$/.test(text)) return 0
  return Number(text)
}

function isImage(content: unknown): boolean {
  if (content && typeof content === 'object' && 'url' in content && (content as { url?: unknown }).url) return true
  if (typeof content !== 'string') return false
  const lowered = content.trim().toLowerCase()
  if (lowered.startsWith('data:image/')) return true
  if (!lowered.startsWith('http')) return false
  return IMAGE_SUFFIXES.some(suffix => lowered.split('?', 1)[0].endsWith(suffix))
}

function channelOf(leases: unknown[]): string {
  for (const lease of leases) {
    const item = lease as { kind?: unknown; identity?: Record<string, unknown> }
    if (String(item.kind || '') !== 'network') continue
    return String(item.identity?.channel || '')
  }
  return ''
}

function peers(
  book: { records: () => Array<{ pid: unknown; status: unknown; leases?: unknown }> } | null,
  record: { pid?: unknown },
  channel: string
): number {
  if (!book || !channel) return 0
  const pid = Number(record.pid || 0)
  let count = 0
  for (const other of book.records()) {
    if (Number(other.pid) === pid) continue
    const status = other.status
    const text =
      typeof status === 'object' && status !== null && 'value' in status
        ? String((status as { value: unknown }).value)
        : String(status ?? '')
    if (text === 'closed' || text === 'closing') continue
    if (channelOf([...(other.leases as unknown[]) || []]) === channel) count += 1
  }
  return count
}
