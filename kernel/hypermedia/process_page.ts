/** The current page for one capability process. */

import { address_scope } from '../communication/address.ts'
import { opaque } from './handle.ts'
import { Link } from './link.ts'
import { Representation } from './representation.ts'

type RecordLike = {
  status?: unknown
  pid?: unknown
  capability_id?: unknown
  leases?: unknown
  started?: unknown
}

export function process_page(
  record: RecordLike,
  activity = '',
  counterpart = '',
  way = '',
  shares: string[] = []
): Representation {
  const status = record.status
  const statusText =
    typeof status === 'object' && status !== null && 'value' in status
      ? String((status as { value: unknown }).value)
      : String(status ?? '')
  const closed = statusText === 'closed'
  const state = closed ? 'closed' : activity || 'sleeping'
  const pid = String(Number(record.pid))
  const links = [new Link('self', pid, pid)]
  if (state === 'with' && counterpart) links.push(new Link('with', counterpart, counterpart))
  if (state === 'sleeping') links.push(new Link('stop', pid, opaque('stop', pid, String(record.started || ''))))
  for (const partner of shares) {
    if (partner && partner !== pid) links.push(new Link('share', partner, partner))
  }
  const scope = address_scope((record.leases as never) || [])
  if (scope) links.push(new Link('memory', scope, scope))
  const facts: Record<string, unknown> = {
    activity: state,
    capability_id: String(record.capability_id),
    pid: Number(record.pid)
  }
  if (state === 'with') facts.way = way
  return new Representation(facts, links)
}

export function page_document(representation: Representation): Record<string, unknown> {
  return {
    facts: { ...representation.facts },
    links: representation.links.map(link => ({ rel: link.relation, resource: link.resource_id }))
  }
}
