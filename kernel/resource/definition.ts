/** Definitions and grants for resources owned by one capability process. */

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

class PyTypeError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'TypeError'
  }
}

function enumValue(value: unknown): string {
  if (typeof value === 'object' && value !== null && 'value' in value) {
    const inner = (value as { value: unknown }).value
    if (typeof inner === 'string' || typeof inner === 'number') return String(inner)
  }
  return String(value ?? '')
}

export class ResourceKind {
  static readonly MEMORY = new ResourceKind('memory')
  static readonly TOOL = new ResourceKind('tool')
  static readonly SANDBOX = new ResourceKind('sandbox')
  static readonly NETWORK = new ResourceKind('network')
  static readonly members = [ResourceKind.MEMORY, ResourceKind.TOOL, ResourceKind.SANDBOX, ResourceKind.NETWORK]

  private constructor(readonly value: string) {}

  toString(): string {
    return this.value
  }
}

export class ResourceShareMode {
  static readonly EXCLUSIVE = new ResourceShareMode('exclusive')
  static readonly SHARED = new ResourceShareMode('shared')

  private constructor(readonly value: string) {}

  toString(): string {
    return this.value
  }
}

export class ResourceDefinition {
  constructor(
    readonly kind: ResourceKind | string,
    readonly required = true,
    readonly share_mode: ResourceShareMode | string = ResourceShareMode.EXCLUSIVE,
    readonly resource_id = ''
  ) {}
}

export class ResourceGrant {
  readonly metadata: Record<string, unknown>
  readonly call_params: Record<string, unknown>

  constructor(
    readonly resource_id: string,
    readonly kind: ResourceKind | string,
    readonly handle: string,
    metadata: Record<string, unknown> = {},
    call_params: Record<string, unknown> = {},
    readonly share_mode: ResourceShareMode | string = ResourceShareMode.EXCLUSIVE
  ) {
    this.metadata = { ...metadata }
    this.call_params = { ...call_params }
  }

  process_payload(): Record<string, unknown> {
    return {
      handle: this.handle,
      kind: kindText(this.kind),
      call_params: { ...this.call_params }
    }
  }

  payload(): Record<string, unknown> {
    return this.process_payload()
  }
}

export function validate_grants(requirements: ResourceDefinition[], grants: ResourceGrant[]): void {
  const handles = grants.map(grant => grant.handle)
  if (new Set(handles).size !== handles.length) throw new ValueError('Resource grants must have unique handles')
  if (requirements.some(requirement => requirement.resource_id)) {
    validateByResourceId(requirements, grants)
    return
  }
  validateByKind(requirements, grants)
}

function validateByKind(requirements: ResourceDefinition[], grants: ResourceGrant[]): void {
  const granted = new Set(grants.map(grant => kindText(grant.kind)))
  if (granted.size !== grants.length) throw new ValueError('Resource grants must have unique kinds')
  for (const requirement of requirements) {
    if (requirement.required && !granted.has(kindText(requirement.kind))) {
      throw new ValueError(`Missing required resource grant: ${kindText(requirement.kind)}`)
    }
  }
  const allowed = new Set(requirements.map(requirement => kindText(requirement.kind)))
  const unknown = [...granted].filter(kind => !allowed.has(kind)).sort()
  if (unknown.length) {
    throw new ValueError(`Capability received undeclared resources: ${unknown.join(', ')}`)
  }
}

function validateByResourceId(requirements: ResourceDefinition[], grants: ResourceGrant[]): void {
  const byId = new Map<string, ResourceGrant>()
  for (const grant of grants) byId.set(grant.resource_id, grant)
  if (byId.size !== grants.length) throw new ValueError('Resource grants must have unique resource ids')
  for (const requirement of requirements) {
    const grant = byId.get(requirement.resource_id)
    if (!grant) {
      if (requirement.required) throw new ValueError(`Missing required resource grant: ${requirement.resource_id}`)
      continue
    }
    if (kindText(grant.kind) !== kindText(requirement.kind)) {
      throw new PyTypeError(
        `Resource '${requirement.resource_id}' expects ${kindText(requirement.kind)}, got ${kindText(grant.kind)}`
      )
    }
  }
  const known = new Set(requirements.map(requirement => requirement.resource_id))
  const unknown = [...byId.keys()].filter(id => !known.has(id)).sort()
  if (unknown.length) throw new ValueError(`Capability received undeclared resources: ${unknown.join(', ')}`)
}

function kindText(kind: unknown): string {
  return enumValue(kind)
}
