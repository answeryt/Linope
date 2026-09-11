import { EMPTY_SHELL, type Message, type Session, type ShellState, type Workspace } from '../types'

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value !== '' ? value : null
}

function idOf(value: unknown): string | null {
  return text(value)
}

function workspace(value: unknown): Workspace | null {
  const row = asRecord(value)
  if (row === null) return null
  const id = idOf(row.id)
  const name = text(row.name)
  if (id === null || name === null) return null
  return { id, name }
}

function session(value: unknown): Session | null {
  const row = asRecord(value)
  if (row === null) return null
  const id = idOf(row.id)
  const title = text(row.title)
  if (id === null || title === null) return null
  const workspaceId = text(row.workspaceId)
  return { id, title, workspaceId }
}

function message(value: unknown): Message | null {
  const row = asRecord(value)
  if (row === null) return null
  const id = idOf(row.id)
  const role = row.role === 'user' || row.role === 'assistant' ? row.role : null
  const textValue = text(row.text)
  if (id === null || role === null || textValue === null) return null
  return { id, role, text: textValue }
}

function list<T>(value: unknown, read: (item: unknown) => T | null): T[] {
  if (!Array.isArray(value)) return []
  const out: T[] = []
  for (const item of value) {
    const parsed = read(item)
    if (parsed !== null) out.push(parsed)
  }
  return out
}

export function parseShell(value: unknown): ShellState {
  const row = asRecord(value)
  if (row === null) return EMPTY_SHELL
  return {
    workspaces: list(row.workspaces, workspace),
    sessions: list(row.sessions, session),
    messages: list(row.messages, message),
    selectedWorkspaceId: text(row.selectedWorkspaceId),
    selectedSessionId: text(row.selectedSessionId),
    model: text(row.model),
    cwd: text(row.cwd),
  }
}

export async function loadShell(): Promise<ShellState> {
  const response = await fetch('/api/shell')
  if (!response.ok) {
    throw new Error(`ui: shell ${response.status}`)
  }
  return parseShell(await response.json())
}
