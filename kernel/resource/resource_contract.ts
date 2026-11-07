/** The only registry of resource kinds. */

import { open_state } from './memory/state.ts'

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

type Open = (identity: Record<string, unknown>) => Record<string, unknown>
type Close = (identity: Record<string, unknown>, state: Record<string, unknown> | null) => void

export function kind_name(kind: unknown): string {
  if (typeof kind === 'object' && kind !== null && 'value' in kind) return String((kind as { value: unknown }).value)
  return String(kind)
}

export class ResourceContract {
  constructor(
    readonly name: string,
    readonly required_identity_keys: string[],
    readonly allow_shared = true,
    readonly open: Open | null = null,
    readonly close: Close | null = null
  ) {}
}

const contracts = new Map<string, ResourceContract>()

export function register(contract: ResourceContract, replace = false): void {
  const name = kind_name(contract.name)
  if (!name || name !== contract.name) throw new ValueError('Resource name must not be empty')
  if (contracts.has(name) && !replace) throw new ValueError(`Resource already registered: ${name}`)
  contracts.set(name, contract)
}

export function unregister(name: string): void {
  contracts.delete(kind_name(name))
}

export function known(name: unknown): boolean {
  return contracts.has(kind_name(name))
}

export function require(name: unknown): ResourceContract {
  const found = contracts.get(kind_name(name))
  if (!found) throw new ValueError(`Unknown resource: ${kind_name(name)}`)
  return found
}

export function names(): string[] {
  return [...contracts.keys()].sort()
}

export function validate_claim(kind: unknown, identity: Record<string, unknown>, shared: boolean): void {
  const contract = require(kind)
  const missing = contract.required_identity_keys.filter(key => !String((identity || {})[key] || '').trim())
  if (missing.length) throw new ValueError(`${contract.name} is missing identity: ${missing.join(', ')}`)
  if (shared && !contract.allow_shared) throw new ValueError(`${contract.name} cannot be shared`)
}

export function open_entity(
  kind: unknown,
  identity: Record<string, unknown>,
  loader?: { load: (kind: string, identity: Record<string, unknown>) => Record<string, unknown> } | null
): Record<string, unknown> {
  const contract = require(kind)
  if (contract.open) return { ...contract.open({ ...identity }) }
  if (loader) return { ...loader.load(kind_name(kind), { ...identity }) }
  return { loaded: true, kind: kind_name(kind), identity: { ...identity } }
}

export function close_entity(
  kind: unknown,
  identity: Record<string, unknown>,
  state: Record<string, unknown> | null,
  loader?: { unload: (kind: string, identity: Record<string, unknown>, state: Record<string, unknown> | null) => void } | null
): void {
  const contract = require(kind)
  if (contract.close) {
    contract.close({ ...identity }, state === null ? null : { ...state })
    return
  }
  if (loader) loader.unload(kind_name(kind), { ...identity }, state)
}

function installBuiltins(): void {
  const builtins = [
    new ResourceContract('memory', ['scope'], true, identity => open_state(identity)),
    new ResourceContract('tool', ['id']),
    new ResourceContract('sandbox', ['root']),
    new ResourceContract('network', ['channel'])
  ]
  for (const contract of builtins) register(contract, true)
}

installBuiltins()
