/** Optional diagnostics, plus the activity trail of capability processes. */

import { randomBytes } from 'node:crypto'

import { ActivityLog } from './activity.ts'

export { ActivityLog }

export class Diagnostic {
  constructor(
    readonly trace_id: string,
    readonly error = '',
    readonly location = '',
    readonly details: Record<string, unknown> | null = null
  ) {}
}

export function new_trace_id(): string {
  return randomBytes(16).toString('hex')
}

export function record_error(error: unknown, location = ''): Diagnostic {
  return new Diagnostic(new_trace_id(), String(error), location)
}
