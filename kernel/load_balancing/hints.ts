/** Read the ledger hints that say which peer process still has room. */

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

export class Seat {
  constructor(
    readonly process_id: string,
    readonly resource_id: string,
    readonly capability_id: string,
    readonly kind: string,
    readonly identity: Record<string, unknown>,
    readonly pending: number,
    readonly claimed: number,
    readonly limits: Record<string, unknown>,
    readonly capacity: number,
    readonly occupied: number,
    readonly window: number | null,
    readonly share_mode: string,
    readonly handle: string,
    readonly rtt_ms = 0
  ) {}

  get budget_full(): boolean {
    return this.window !== null && this.occupied > this.window
  }

  get has_room(): boolean {
    return !this.budget_full && this.claimed < this.capacity
  }
}

type SeatRow = {
  process_id: string
  resource_id: string
  capability_id: string
  kind: string
  identity: Record<string, unknown>
  pending: number
  claimed: number
  limits: Record<string, unknown>
  capacity: number
  occupied: number
  window: number | null
  share_mode: string
  handle: string
  rtt_ms?: number
}

type SeatStore = {
  capability_seats: (capability: string) => SeatRow[]
  resource_seats: (kind: string, identity: Record<string, unknown>) => SeatRow[]
}

export function seats(store: SeatStore, kind: string, identity: Record<string, unknown>): Seat[] {
  const raw = kind ? store.resource_seats(kind, { ...identity }) : store.capability_seats(String(identity.capability || ''))
  return raw.map(
    item =>
      new Seat(
        item.process_id,
        item.resource_id,
        item.capability_id,
        item.kind,
        item.identity,
        item.pending,
        item.claimed,
        item.limits,
        item.capacity,
        item.occupied,
        item.window,
        item.share_mode,
        item.handle,
        item.rtt_ms ?? 0
      )
  )
}

export function one_resource(found: Seat[]): Seat[] {
  if (!found.length) return []
  const ids = new Set(found.map(item => item.resource_id))
  if (ids.size !== 1) throw new ValueError('These processes do not share one resource and cannot split work')
  return found
}
