/** Pick the peer process with more room. */

import { Seat } from './hints.ts'

export function choose(candidates: Seat[]): Seat | null {
  const openSeats = candidates.filter(seat => seat.has_room)
  if (!openSeats.length) return null
  if (openSeats.length <= 2) return openSeats.reduce((best, seat) => (loadKeyLess(seat, best) ? seat : best))
  const [left, right] = sample(openSeats, 2)
  return loadKeyLess(left, right) || loadKeyEqual(left, right) ? left : right
}

export function load_key(seat: Seat): [number, number, number, string] {
  return [seat.claimed, seat.pending, Number(seat.rtt_ms || 0), seat.process_id]
}

function loadKeyLess(left: Seat, right: Seat): boolean {
  const [a, b] = [load_key(left), load_key(right)]
  for (let index = 0; index < a.length; index += 1) {
    if (a[index] < b[index]) return true
    if (a[index] > b[index]) return false
  }
  return false
}

function loadKeyEqual(left: Seat, right: Seat): boolean {
  const [a, b] = [load_key(left), load_key(right)]
  return a.every((item, index) => item === b[index])
}

function sample<T>(items: T[], count: number): T[] {
  const copy = [...items]
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(Math.random() * (index + 1))
    ;[copy[index], copy[swap]] = [copy[swap], copy[index]]
  }
  return copy.slice(0, count)
}
