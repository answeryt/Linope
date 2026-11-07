/** Open or stop peer processes. Starting still goes through the reconciler. */

import { Seat } from './hints.ts'
import { load_key } from './pick.ts'

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

export function reconciler_opener(
  reconciler: { start: (declaration: unknown, threadPolicy?: unknown) => { activation: { process_id: unknown } } },
  declaration: unknown,
  threadPolicy: unknown = null
): () => string {
  return () => String(reconciler.start(declaration, threadPolicy).activation.process_id)
}

export function open_peer(opener: () => string, current: number, ceiling: number): string {
  if (ceiling < 1) throw new ValueError('Process limit must be at least 1')
  if (current >= ceiling) throw new ValueError('Process count is already at the limit')
  return opener()
}

export function close_idle(
  store: { services_for_process?: (processId: string) => unknown; set_desired: (processId: string, desired: string) => void },
  found: Seat[],
  floor: number,
  keep: string | null = null
): string[] {
  if (floor < 0) throw new ValueError('Minimum process count cannot be negative')
  const idle = found.filter(seat => seat.process_id !== keep && seat.pending === 0 && seat.claimed === 0)
  idle.sort((left, right) => {
    const a = load_key(left)
    const b = load_key(right)
    for (let index = 0; index < a.length; index += 1) {
      if (a[index] === b[index]) continue
      return a[index] < b[index] ? 1 : -1
    }
    return 0
  })
  let canClose = Math.max(0, found.length - floor)
  const closed: string[] = []
  for (const seat of idle) {
    if (canClose <= 0) break
    if (typeof store.services_for_process === 'function' && store.services_for_process(seat.process_id)) continue
    store.set_desired(seat.process_id, 'stop')
    closed.push(seat.process_id)
    canClose -= 1
  }
  return closed
}
