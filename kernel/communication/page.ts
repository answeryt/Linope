/** The model page: a projection of one pointer space plus the actions offered now. */

import { opaque } from '../hypermedia/handle.ts'
import { Link } from '../hypermedia/link.ts'
import { ANSWER, memory_page } from '../hypermedia/memory_page.ts'
import { Representation } from '../hypermedia/representation.ts'

export class CommandOffer {
  readonly schema: Record<string, unknown>

  constructor(
    readonly way: string,
    readonly capability: string,
    readonly pid = 0,
    schema: Record<string, unknown> = {}
  ) {
    this.schema = { ...schema }
  }

  get relation(): string {
    return `${this.way}:${this.capability}`
  }

  get pointer(): string {
    if (this.way === 'start') return `process start ${this.capability}`
    if (this.way === 'ask') return `ask ${this.pid} -- `
    return `load tool ${this.pid} -- `
  }
}

export function model_page(
  rows: Array<Record<string, unknown>>,
  options: {
    scope: string
    seq: number
    commands?: CommandOffer[]
    read?: Array<Record<string, unknown>> | null
    state?: string | null
  }
): Representation {
  const page = memory_page(rows, {
    scope: options.scope,
    seq: options.seq,
    read: options.read,
    state: options.state
  })
  const facts = { ...page.facts }
  const details: Record<string, Record<string, unknown>> = { ...((facts.details as Record<string, Record<string, unknown>>) || {}) }
  const links = [...page.links]
  for (const offer of options.commands || []) {
    links.push(new Link(offer.relation, offer.pointer, opaque(options.scope, options.seq, offer.pointer)))
    const detail: Record<string, unknown> = { capability: offer.capability }
    const modelPrefix = 'model' + '.'
    if (offer.way === 'start' && String(offer.capability).startsWith(modelPrefix)) detail.with = 'memory=<identity>'
    if (offer.pid) detail.pid = offer.pid
    if (Object.keys(offer.schema).length) detail.schema = offer.schema
    details[offer.relation] = detail
  }
  if (options.scope) {
    links.push(new Link('memory', options.scope, opaque(options.scope, options.seq, 'memory')))
    details.memory = { scope: options.scope }
  }
  links.push(new Link(ANSWER, ANSWER, opaque(options.scope, options.seq, ANSWER)))
  facts.details = details
  return new Representation(facts, links)
}
