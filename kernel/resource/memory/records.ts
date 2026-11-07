/** Shapes for logical memory. These are not physical pages. */

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

export const KIND_CLASS: Record<string, string> = {
  user: 'message',
  model: 'message',
  tool: 'artifact',
  other: 'task'
}
export const STATES = ['asked', 'continue', 'resulted', 'rejected', 'answered'] as const
export const RESIDENT = ['resident', 'cold', 'pinned'] as const

export function class_of(kind: string): string {
  if (!(kind in KIND_CLASS)) throw new ValueError(`Unknown memory: ${kind}`)
  return KIND_CLASS[kind]
}

export class MemoryRow {
  constructor(
    readonly real: string,
    readonly class_name: string,
    readonly kind: string,
    readonly content: string,
    readonly time: string,
    readonly seq: number,
    readonly state = '',
    readonly tokens = 0,
    readonly version = 1
  ) {}

  view(address: string, name: string): Record<string, unknown> {
    const found: Record<string, unknown> = {
      address,
      real: this.real,
      name,
      kind: this.kind,
      content: this.content,
      time: this.time,
      seq: this.seq
    }
    if (this.state) found.state = this.state
    return found
  }
}

export class MemoryBlock {
  constructor(
    readonly resource_id: string,
    readonly reals: string[],
    readonly tokens: number,
    readonly version: number,
    readonly resident = 'cold'
  ) {
    if (!(RESIDENT as readonly string[]).includes(this.resident)) {
      throw new ValueError(`Unknown residency: ${this.resident}`)
    }
  }
}

export class PageTableEntry {
  constructor(
    readonly pid: string,
    readonly resource_id: string,
    readonly class_name: string,
    readonly position: number,
    readonly real: string,
    readonly resident = 'cold',
    readonly version = 1,
    readonly last_access = 0
  ) {}
}

export class PromptFootprint {
  constructor(
    readonly context_limit: number,
    readonly system_tokens = 0,
    readonly message_tokens = 0,
    readonly action_tokens = 0,
    readonly read_tokens = 0,
    readonly output_reserve = 0,
    readonly safety_margin = 0
  ) {}

  get used(): number {
    return this.system_tokens + this.message_tokens + this.action_tokens + this.read_tokens
  }

  get available(): number {
    return this.context_limit - this.used - this.output_reserve - this.safety_margin
  }

  get over_hard_limit(): boolean {
    return this.context_limit > 0 && this.used + this.output_reserve + this.safety_margin > this.context_limit
  }
}
