export type KernelEvent = {
  version: 1
  kind: string
  seq: number
  data: Record<string, unknown>
  request_id?: string
  turn_id?: string
  pid?: number
}

const recordOf = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null

export function parseKernelEvent(line: string): KernelEvent {
  const payload = recordOf(JSON.parse(line))
  if (!payload || payload.version !== 1 || typeof payload.kind !== 'string') {
    throw new Error('Unsupported kernel event')
  }
  const seq = payload.seq
  if (typeof seq !== 'number' || !Number.isInteger(seq) || seq < 1) {
    throw new Error('Kernel event has an invalid sequence')
  }
  const data = recordOf(payload.data)
  if (!data) {
    throw new Error('Kernel event has invalid data')
  }
  let requestId: string | undefined
  if (payload.request_id !== undefined) {
    if (typeof payload.request_id !== 'string') {
      throw new Error('Kernel event has an invalid request id')
    }
    requestId = payload.request_id
  }
  let turnId: string | undefined
  if (payload.turn_id !== undefined) {
    if (typeof payload.turn_id !== 'string') {
      throw new Error('Kernel event has an invalid turn id')
    }
    turnId = payload.turn_id
  }
  let pid: number | undefined
  if (payload.pid !== undefined) {
    const rawPid = payload.pid
    if (typeof rawPid !== 'number' || !Number.isInteger(rawPid) || rawPid <= 0) {
      throw new Error('Kernel event has an invalid pid')
    }
    pid = rawPid
  }
  return {
    data,
    kind: payload.kind,
    pid,
    request_id: requestId,
    seq,
    turn_id: turnId,
    version: 1
  }
}
