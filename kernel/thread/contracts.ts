/** Contracts for execution inside one capability process. */

import { randomUUID } from 'node:crypto'

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

export class ThreadPolicy {
  constructor(
    readonly max_concurrent_tasks = 1,
    readonly min_concurrent_tasks = 1,
    readonly max_sync_workers = 1,
    readonly claim_lease_seconds = 120,
    readonly shutdown_timeout_seconds = 5,
    readonly poll_interval_seconds = 0.05,
    readonly session_affinity = false
  ) {
    if (this.max_concurrent_tasks < 1) throw new ValueError('max_concurrent_tasks must be at least 1')
    if (this.min_concurrent_tasks < 1) throw new ValueError('min_concurrent_tasks must be at least 1')
    if (this.min_concurrent_tasks > this.max_concurrent_tasks) {
      throw new ValueError('min_concurrent_tasks cannot exceed max_concurrent_tasks')
    }
    if (this.max_sync_workers < 0) throw new ValueError('max_sync_workers must not be negative')
    if (this.claim_lease_seconds <= 0) throw new ValueError('claim_lease_seconds must be positive')
    if (this.shutdown_timeout_seconds < 0) throw new ValueError('shutdown_timeout_seconds must not be negative')
    if (this.poll_interval_seconds < 0) throw new ValueError('poll_interval_seconds must not be negative')
  }

  payload(): Record<string, unknown> {
    return {
      max_concurrent_tasks: this.max_concurrent_tasks,
      min_concurrent_tasks: this.min_concurrent_tasks,
      max_sync_workers: this.max_sync_workers,
      claim_lease_seconds: this.claim_lease_seconds,
      shutdown_timeout_seconds: this.shutdown_timeout_seconds,
      poll_interval_seconds: this.poll_interval_seconds,
      session_affinity: this.session_affinity
    }
  }

  static from_payload(payload?: Record<string, unknown> | null): ThreadPolicy {
    const raw = { ...(payload || {}) }
    return new ThreadPolicy(
      Number(raw.max_concurrent_tasks ?? 1),
      Number(raw.min_concurrent_tasks ?? 1),
      Number(raw.max_sync_workers ?? 1),
      Number(raw.claim_lease_seconds ?? 120),
      Number(raw.shutdown_timeout_seconds ?? 5),
      Number(raw.poll_interval_seconds ?? 0.05),
      Boolean(raw.session_affinity ?? false)
    )
  }
}

export class ClaimedRequest {
  readonly claim_token: string

  constructor(
    readonly request_id: string,
    readonly process_id: string,
    readonly body: Record<string, unknown>,
    claimToken = randomUUID().replaceAll('-', ''),
    readonly worker_id = ''
  ) {
    this.claim_token = claimToken
  }
}

export type ThreadInbox = {
  claim: (processId: string, workerId: string, leaseSeconds: number) => ClaimedRequest | null
  complete: (requestId: string, reply: Record<string, unknown>, claimToken?: string | null) => void
  lookup: (requestId: string) => Record<string, unknown> | null
}
