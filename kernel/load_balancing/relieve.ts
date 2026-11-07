/** Add one helper when calculated pressure says this process needs it. */

import { Pressure } from '../calculate/measure.ts'

type Record = { room: Record<string, unknown> }
type Book = {
  get: (pid: number) => Record | null
  save: () => void
}

export function relieve(book: Book, pid: number, pressure: Pressure, delegating: boolean): number {
  const record = book.get(Number(pid))
  if (!record) return 1
  const room = { ...record.room }
  const current = Number(room.worker_ceiling || 1)
  if (pressure.activity === 'closed' || !needed(pressure, delegating)) return current
  const updated = current + 1
  room.worker_ceiling = updated
  record.room = room
  book.save()
  return updated
}

function needed(pressure: Pressure, delegating: boolean): boolean {
  if (pressure.peers > 0 && pressure.activity === 'with') return true
  return delegating && (pressure.activity === 'self' || pressure.activity === 'with')
}
