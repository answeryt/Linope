/** Opaque link handles. Knowing a pid or an address is not the right to follow it. */

import { createHmac, randomBytes } from 'node:crypto'

const key = randomBytes(32)

export function opaque(...parts: unknown[]): string {
  const text = parts.map(part => String(part)).join('\x1f')
  return createHmac('sha256', key).update(text, 'utf8').digest('hex').slice(0, 32)
}
