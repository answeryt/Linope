/** The rows this turn is showing. Older memory is not linked from the page. */

import { Representation } from './representation.ts'

export const ANSWER = 'answer'

export function memory_page(
  rows: Array<Record<string, unknown>>,
  options: { scope: string; seq: number; read?: Array<Record<string, unknown>> | null; state?: string | null }
): Representation {
  void options.scope
  const shown = (options.read != null ? options.read : rows).map(publicRow)
  return new Representation({
    state: options.state || pageState(shown),
    seq: Number(options.seq),
    rows: shown
  })
}

export function page_document(page: Representation): Record<string, unknown> {
  const facts = { ...page.facts }
  const details = (facts.details as Record<string, Record<string, unknown>> | undefined) || {}
  delete facts.details
  const document: Record<string, unknown> = { state: facts.state, seq: facts.seq }
  delete facts.state
  delete facts.seq
  Object.assign(document, facts)
  const links: Record<string, unknown> = {}
  for (const link of page.links) {
    links[link.relation] = { pointer: link.resource_id, handle: link.handle, ...(details[link.relation] || {}) }
  }
  document._links = links
  return document
}

export function allowed_pointers(page: Representation): string[] {
  return page.links.map(link => link.resource_id)
}

function publicRow(row: Record<string, unknown>): Record<string, unknown> {
  const item: Record<string, unknown> = {
    kind: String(row.kind || ''),
    content: String(row.content || '')
  }
  if (row.address) item.address = String(row.address)
  if (row.time) item.time = String(row.time)
  if (row.state) item.state = String(row.state)
  return item
}

function pageState(rows: Array<Record<string, unknown>>): string {
  const newest = rows.length ? rows[rows.length - 1] : null
  if (newest == null) return 'asked'
  return String(newest.state || 'asked')
}
