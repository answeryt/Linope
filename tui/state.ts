import type { KernelEvent } from './link/protocol.js'

export type UiTurn = {
  role: 'assistant' | 'error' | 'system' | 'user'
  stream?: boolean
  text: string
}

export type UiProcess = {
  id: string
  capability: string
  activity: 'waiting' | 'busy' | 'away'
}

export type UiState = {
  cwd: string
  clerk: 'here' | 'away'
  processes: UiProcess[]
  status: 'ready' | 'running'
  turns: UiTurn[]
  activeTurns: Set<string>
}

export function initialUiState(cwd: string): UiState {
  return {
    activeTurns: new Set(),
    clerk: 'here',
    cwd,
    processes: [],
    status: 'ready',
    turns: []
  }
}

export function reduceKernelEvent(state: UiState, event: KernelEvent): UiState {
  const next: UiState = {
    ...state,
    activeTurns: new Set(state.activeTurns),
    processes: state.processes.map(process => ({ ...process })),
    turns: [...state.turns]
  }
  switch (event.kind) {
    case 'session.started':
      next.clerk = 'here'
      next.cwd = textOf(event.data.cwd) || next.cwd
      return next
    case 'session.closed':
      next.clerk = 'away'
      next.processes = []
      next.status = 'ready'
      return next
    case 'process.started':
      if (event.pid === undefined) return next
      upsertProcess(next, String(event.pid), textOf(event.data.capability), 'waiting')
      return next
    case 'process.activity':
      if (event.pid === undefined) return next
      upsertProcess(
        next,
        String(event.pid),
        textOf(event.data.capability),
        activityOf(event.data.activity)
      )
      if (activityOf(event.data.activity) === 'away') {
        next.processes = next.processes.filter(process => process.id !== String(event.pid))
      }
      return next
    case 'process.closed':
      if (event.pid !== undefined) {
        next.processes = next.processes.filter(process => process.id !== String(event.pid))
      }
      return next
    case 'turn.started':
      if (event.turn_id) next.activeTurns.add(event.turn_id)
      next.status = 'running'
      return next
    case 'model.delta':
      appendStream(next, textOf(event.data.text))
      return next
    case 'turn.completed':
      if (event.turn_id) next.activeTurns.delete(event.turn_id)
      completeTurn(next, event)
      next.status = next.activeTurns.size ? 'running' : 'ready'
      return next
    case 'command.completed':
      showCommandValue(next, event)
      next.status = next.activeTurns.size ? 'running' : 'ready'
      return next
    case 'command.failed':
      appendError(next, errorText(event.data.error))
      next.status = next.activeTurns.size ? 'running' : 'ready'
      return next
    case 'protocol.error':
    case 'diagnostic':
      appendError(next, textOf(event.data.message) || 'Invalid kernel event')
      return next
    case 'capability.notice':
      if (event.data.kind === 'agent.progress') {
        appendSystem(next, textOf(event.data.text))
      }
      return next
    default:
      return next
  }
}

function completeTurn(state: UiState, event: KernelEvent): void {
  const error = event.data.error
  if (error) {
    appendError(state, errorText(error))
    return
  }
  const result = event.data.result
  const text = modelText(result)
  if (!text) return
  const last = state.turns.at(-1)
  if (last?.role === 'assistant' && last.stream) {
    state.turns[state.turns.length - 1] = { role: 'assistant', text }
  } else {
    state.turns.push({ role: 'assistant', text })
  }
}

function appendStream(state: UiState, text: string): void {
  if (!text) return
  const last = state.turns.at(-1)
  if (last?.role === 'assistant' && last.stream) {
    state.turns[state.turns.length - 1] = {
      role: 'assistant',
      stream: true,
      text: `${last.text}${text}`
    }
    return
  }
  state.turns.push({ role: 'assistant', stream: true, text })
}

function appendError(state: UiState, text: string): void {
  if (text) state.turns.push({ role: 'error', text })
}

function appendSystem(state: UiState, text: string): void {
  if (text) state.turns.push({ role: 'system', text })
}

function showCommandValue(state: UiState, event: KernelEvent): void {
  const command = textOf(event.data.command)
  if (!command || command.startsWith('process start')) return
  const value = event.data.value
  if (value === undefined || value === null || value === 0) return
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  appendSystem(state, text)
}

function upsertProcess(
  state: UiState,
  id: string,
  capability: string,
  activity: UiProcess['activity']
): void {
  const found = state.processes.find(process => process.id === id)
  if (found) {
    if (capability) found.capability = capability
    found.activity = activity
  } else {
    state.processes.push({ activity, capability, id })
  }
}

function activityOf(value: unknown): UiProcess['activity'] {
  const activity = textOf(value)
  if (activity === 'working' || activity === 'busy') return 'busy'
  if (activity === 'sleeping' || activity === 'waiting') return 'waiting'
  return 'away'
}

function modelText(value: unknown): string {
  const payload = typeof value === 'string' ? parseJson(value) : value
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    const blocks = (payload as { blocks?: unknown }).blocks
    if (Array.isArray(blocks)) {
      return blocks
        .filter(
          (block): block is { type: string; text?: unknown } =>
            Boolean(block) && typeof block === 'object' && (block as { type?: unknown }).type === 'text'
        )
        .map(block => textOf(block.text))
        .filter(Boolean)
        .join('\n')
    }
  }
  if (typeof value === 'string') return value
  return value === undefined || value === null ? '' : JSON.stringify(value)
}

function parseJson(value: string): unknown {
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

function textOf(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function errorText(value: unknown): string {
  if (value && typeof value === 'object') {
    const message = (value as { message?: unknown }).message
    if (typeof message === 'string') return message
  }
  return textOf(value)
}
