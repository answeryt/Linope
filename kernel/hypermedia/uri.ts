/** Opaque local resource URI formatting and parsing. */

import { Link } from './link.ts'

const RESOURCE_PREFIX = '/resources/'
const PAGE_ACTIONS = new Set(['pin', 'swap', 'admit'])
const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '::1'])

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

export function resource_uri(link: Link, baseUrl: string): string {
  if (!link.handle) throw new ValueError('a resource URI requires a link handle')
  const parts = new URL(baseUrl.replace(/\/+$/, ''))
  if ((parts.protocol !== 'http:' && parts.protocol !== 'https:') || !parts.host) {
    throw new ValueError('resource base URL must use HTTP or HTTPS')
  }
  const origin = `${parts.protocol}//${parts.host}${parts.pathname.replace(/\/+$/, '')}`
  return `${origin}${RESOURCE_PREFIX}${encodeURIComponent(link.handle)}`
}

export function content_uri(link: Link, baseUrl: string): string {
  return `${resource_uri(link, baseUrl)}/content`
}

export function action_uri(link: Link, baseUrl: string): string {
  if (!PAGE_ACTIONS.has(link.relation)) throw new ValueError('resource action must be pin, swap, or admit')
  return `${resource_uri(link, baseUrl)}/${link.relation}`
}

export function parse_resource_uri(value: string): string {
  const parts = parseLocal(value)
  const segments = pathSegments(parts.pathname)
  if (segments.length !== 2 || segments[0] !== 'resources') {
    throw new ValueError('resource URI must have the form /resources/<id>')
  }
  return validateHandle(segments[1])
}

export function parse_content_uri(value: string): string {
  const parts = parseLocal(value)
  const segments = pathSegments(parts.pathname)
  if (segments.length !== 3 || segments[0] !== 'resources' || segments[2] !== 'content') {
    throw new ValueError('content URI must have the form /resources/<id>/content')
  }
  return validateHandle(segments[1])
}

export function parse_action_uri(value: string): [string, string] {
  const parts = parseLocal(value)
  const segments = pathSegments(parts.pathname)
  if (segments.length !== 3 || segments[0] !== 'resources') {
    throw new ValueError('action URI must have the form /resources/<id>/<action>')
  }
  if (!PAGE_ACTIONS.has(segments[2])) throw new ValueError('resource action must be pin, swap, or admit')
  return [validateHandle(segments[1]), segments[2]]
}

function parseLocal(value: string): URL {
  let parts: URL
  try {
    parts = new URL(value)
  } catch {
    throw new ValueError('resource URI must use HTTP or HTTPS')
  }
  if (parts.protocol !== 'http:' && parts.protocol !== 'https:') {
    throw new ValueError('resource URI must use HTTP or HTTPS')
  }
  if (!LOOPBACK_HOSTS.has(parts.hostname)) {
    throw new ValueError('resource URI must target the local Linope server')
  }
  if (parts.search || parts.hash) throw new ValueError('resource URI cannot contain a query or fragment')
  return parts
}

function pathSegments(file: string): string[] {
  return file
    .split('/')
    .filter(Boolean)
    .map(segment => decodeURIComponent(segment))
}

function validateHandle(value: string): string {
  if (!value || [...value].some(char => !'0123456789abcdefABCDEF'.includes(char))) {
    throw new ValueError('resource URI contains an invalid opaque id')
  }
  return value
}
