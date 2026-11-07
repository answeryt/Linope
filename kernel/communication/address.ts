/** Forwards memory calls to kernel.scheduler. */

import { CLASSES } from '../scheduler/memory_space.ts'

export { CLASSES }

type Lease = {
  kind?: unknown
  identity?: Record<string, unknown>
  metadata?: { identity?: Record<string, unknown> }
}

export function address_scope(leases: Iterable<Lease> | null | undefined): string {
  for (const item of leases || []) {
    if (kindOf(item) !== 'memory') continue
    return String(identityOf(item).scope || '')
  }
  return ''
}

function kindOf(item: Lease): string {
  const kind = item?.kind
  if (typeof kind === 'object' && kind !== null && 'value' in kind) return String((kind as { value: unknown }).value)
  return String(kind ?? '')
}

function identityOf(item: Lease): Record<string, unknown> {
  if (item.identity && typeof item.identity === 'object') return item.identity
  const nested = item.metadata?.identity
  if (nested) return nested
  return {}
}
