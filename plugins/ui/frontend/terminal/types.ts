export type Role = 'assistant' | 'system' | 'tool' | 'user'
export type DetailsMode = 'hidden' | 'collapsed' | 'expanded'
export type IndicatorStyle = 'kaomoji' | 'emoji' | 'ascii' | 'unicode'
export type StatusBarMode = 'top' | 'bottom' | 'off'
export type OverlayKind = 'none' | 'sessions' | 'model' | 'confirm' | 'help'

export type MsgKind = 'diff' | 'event' | 'intro' | 'panel' | 'slash' | 'trail' | 'chat'

export interface PanelSection {
  items?: string[]
  rows?: [string, string][]
  text?: string
  title?: string
}

export interface PanelData {
  sections: PanelSection[]
  title: string
}

export interface Usage {
  calls: number
  compressions: number
  context_max: number
  context_percent: number
  context_used: number
  input: number
  output: number
  total: number
}

export interface SessionInfo {
  cwd: string
  model: string
  profile_name: string
  skills: string[]
  tools: string[]
  version: string
}

export interface Msg {
  id: string
  info?: SessionInfo
  kind: MsgKind
  panel?: PanelData
  role: Role
  text: string
  thinking?: string
  tools?: string[]
}

export interface Completion {
  help: string
  text: string
}

export interface QueuedDraft {
  id: string
  text: string
}

export interface ConfirmReq {
  cancelLabel: string
  confirmLabel: string
  detail: string
  title: string
}

export interface SlashCommand {
  aliases?: string[]
  help: string
  name: string
  usage?: string
}

export const EMPTY_USAGE: Usage = {
  calls: 0,
  compressions: 0,
  context_max: 128000,
  context_percent: 0,
  context_used: 0,
  input: 0,
  output: 0,
  total: 0,
}
