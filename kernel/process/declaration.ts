/** Nested resource declaration used to create one capability process. */

import { CLASSES } from '../communication/address.ts'
import { ResourceDefinition } from '../resource/definition.ts'
import { kind_name, require } from '../resource/resource_contract.ts'

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

export class ResourceClaim {
  readonly identity: Record<string, unknown>
  readonly call_params: Record<string, unknown>

  constructor(
    readonly kind: unknown,
    identity: Record<string, unknown> = {},
    call_params: Record<string, unknown> = {}
  ) {
    this.identity = { ...identity }
    this.call_params = { ...call_params }
  }

  static from_payload(payload: Record<string, unknown>): ResourceClaim {
    return new ResourceClaim(
      String(payload.kind),
      { ...((payload.identity as Record<string, unknown>) || {}) },
      { ...((payload.call_params as Record<string, unknown>) || {}) }
    )
  }
}

export class ProcessDeclaration {
  readonly resources: ResourceClaim[]
  readonly settings: Record<string, unknown>

  constructor(
    readonly capability: string,
    resources: ResourceClaim[] = [],
    settings: Record<string, unknown> = {}
  ) {
    this.resources = [...resources]
    this.settings = { ...settings }
  }

  resource_definitions(): ResourceDefinition[] {
    return this.resources.map(claim => new ResourceDefinition(claim.kind as string))
  }

  static from_payload(payload: Record<string, unknown>): ProcessDeclaration {
    const raw = (payload.resources as Array<Record<string, unknown>>) || []
    return new ProcessDeclaration(
      String(payload.capability),
      raw.map(item => ResourceClaim.from_payload(item)),
      { ...((payload.settings as Record<string, unknown>) || {}) }
    )
  }
}

export function stamp_memory_space(
  declaration: ProcessDeclaration,
  changes?: Array<[string, unknown]> | null
): ProcessDeclaration {
  let space = ''
  for (const [topic, raw] of changes || []) {
    if (topic === 'space' && String(raw).trim()) space = String(raw).trim()
  }
  if (!space) return declaration
  for (const part of space.replaceAll(' ', '').split(',')) {
    if (!(CLASSES as readonly string[]).includes(part)) throw new ValueError(`Unknown memory class: ${part || space}`)
  }
  const updated = declaration.resources.map(claim => {
    if (kind_name(claim.kind) !== 'memory') return claim
    return new ResourceClaim(claim.kind, claim.identity, { ...claim.call_params, space })
  })
  return new ProcessDeclaration(declaration.capability, updated, declaration.settings)
}

export function append_chosen(declaration: ProcessDeclaration, chosen: string[]): ProcessDeclaration {
  if (!chosen.length) return declaration
  const existing = new Set(declaration.resources.map(item => kind_name(item.kind)))
  const added: ResourceClaim[] = []
  for (const raw of chosen) {
    const claim = chosenClaim(raw, existing)
    added.push(claim)
    existing.add(kind_name(claim.kind))
  }
  return new ProcessDeclaration(declaration.capability, [...declaration.resources, ...added], declaration.settings)
}

function chosenClaim(raw: string, existing: Set<string>): ResourceClaim {
  const sep = raw.indexOf('=')
  const kind = sep < 0 ? raw : raw.slice(0, sep)
  const value = sep < 0 ? '' : raw.slice(sep + 1)
  const name = kind_name(kind.trim())
  const identityValue = value.trim()
  if (sep < 0 || !name || !identityValue) throw new ValueError('Missing identity')
  if (existing.has(name)) throw new ValueError(`Cannot change the default resource: ${name}`)
  const contract = require(name)
  if (contract.required_identity_keys.length !== 1) {
    throw new ValueError(`${name} is missing identity: ${contract.required_identity_keys.join(', ')}`)
  }
  return new ResourceClaim(name, { [contract.required_identity_keys[0]]: identityValue })
}
