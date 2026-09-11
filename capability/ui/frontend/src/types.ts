export type Workspace = {
  id: string
  name: string
}

export type Session = {
  id: string
  title: string
  workspaceId: string | null
}

export type Message = {
  id: string
  role: 'user' | 'assistant'
  text: string
}

export type ShellState = {
  workspaces: Workspace[]
  sessions: Session[]
  messages: Message[]
  selectedWorkspaceId: string | null
  selectedSessionId: string | null
  model: string | null
  cwd: string | null
}

export const EMPTY_SHELL: ShellState = {
  workspaces: [],
  sessions: [],
  messages: [],
  selectedWorkspaceId: null,
  selectedSessionId: null,
  model: null,
  cwd: null,
}
