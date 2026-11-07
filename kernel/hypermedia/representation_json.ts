/** JSON projection for the minimal local resource representation. */

import { Link } from './link.ts'
import { Representation } from './representation.ts'
import { action_uri, content_uri, resource_uri } from './uri.ts'

const GET_RELATIONS = new Set(['self', 'content'])
const PAGE_ACTIONS = new Set(['pin', 'swap', 'admit'])

export const RELATIONS: Record<string, Set<string>> = {
  file: new Set(['self', 'content', 'pin', 'swap', 'admit']),
  resource: new Set(['self', 'content', 'pin', 'swap', 'admit'])
}

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

export function link_payload(link: Link, baseUrl: string, resourceType = 'file'): Record<string, string> {
  const allowed = RELATIONS[resourceType]
  if (!allowed) throw new ValueError(`unsupported resource type: ${resourceType}`)
  if (!allowed.has(link.relation)) throw new ValueError(`unsupported ${resourceType} relation: ${link.relation}`)
  let href: string
  let mediaType: string
  if (link.relation === 'content') {
    href = content_uri(link, baseUrl)
    mediaType = 'text/plain; charset=utf-8'
  } else if (PAGE_ACTIONS.has(link.relation)) {
    href = action_uri(link, baseUrl)
    mediaType = 'application/json'
  } else if (link.relation === 'self') {
    href = resource_uri(link, baseUrl)
    mediaType = 'application/json'
  } else {
    throw new ValueError(`unsupported resource relation: ${link.relation}`)
  }
  return {
    rel: link.relation,
    href,
    method: GET_RELATIONS.has(link.relation) ? 'GET' : 'POST',
    type: mediaType
  }
}

export function representation_payload(
  representation: Representation,
  baseUrl: string,
  resourceType = 'resource',
  resourceId: string | null = null
): Record<string, unknown> {
  const payload: Record<string, unknown> = { ...representation.facts, type: resourceType }
  if (resourceId !== null) payload.id = resourceId
  const links: Record<string, unknown> = {}
  for (const link of representation.links) links[link.relation] = link_payload(link, baseUrl, resourceType)
  payload._links = links
  return payload
}

export function links_for_state(file: string, handle: string, state: string): Link[] {
  const selfLink = new Link('self', file, handle)
  if (state === 'swapped') return [selfLink, new Link('admit', file, handle)]
  if (state === 'pinned') return [selfLink, new Link('content', file, handle)]
  return [
    selfLink,
    new Link('content', file, handle),
    new Link('pin', file, handle),
    new Link('swap', file, handle)
  ]
}

export function file_resource_payload(file: string, handle: string, state: string, baseUrl: string): Record<string, unknown> {
  return representation_payload(
    new Representation({ state }, links_for_state(file, handle, state)),
    baseUrl,
    'file',
    handle
  )
}

export function content_payload(options: {
  path: string
  handle: string
  state: string
  content: string
  baseUrl: string
}): Record<string, unknown> {
  const payload = file_resource_payload(options.path, options.handle, options.state, options.baseUrl)
  payload.content = options.content
  return payload
}
