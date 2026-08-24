import { loadShell } from '../src/api/shell'
import type { ShellState } from '../src/types'
import { dailyFortune, FACES, randomFortune } from './content'
import { filterCompletions, looksLikeSlashCommand, newId, parseSlashCommand } from './domain'
import { findSlashCommand, slashCatalog, slashHelpSections, type SlashResult } from './slash'
import { DARK_THEME, LIGHT_THEME, themeForProduct, type Theme } from './theme'
import type {
  Completion,
  ConfirmReq,
  DetailsMode,
  IndicatorStyle,
  Msg,
  OverlayKind,
  QueuedDraft,
  SessionInfo,
  StatusBarMode,
  Usage,
} from './types'
import { EMPTY_USAGE } from './types'

export interface TerminalSession {
  id: string
  messages: Msg[]
  startedAt: number
  title: string
}

export interface TerminalState {
  busy: boolean
  compact: boolean
  completions: Completion[]
  compIdx: number
  confirm: ConfirmReq | null
  cwd: string
  detailsMode: DetailsMode
  history: string[]
  historyIdx: number
  indicator: IndicatorStyle
  input: string
  lastTurnEndedAt: number | null
  model: string
  overlay: OverlayKind
  placeholder: string
  product: string
  queue: QueuedDraft[]
  queueEditIdx: number
  selectedSessionId: string
  sessions: TerminalSession[]
  status: string
  statusBar: StatusBarMode
  theme: Theme
  turnStartedAt: number | null
  usage: Usage
}

export type Listener = () => void

const DETAILS: DetailsMode[] = ['hidden', 'collapsed', 'expanded']
const INDICATORS: IndicatorStyle[] = ['kaomoji', 'emoji', 'ascii', 'unicode']

function emptySession(title = 'session'): TerminalSession {
  return { id: newId(), messages: [], startedAt: Date.now(), title }
}

function sessionInfo(state: TerminalState): SessionInfo {
  return {
    cwd: state.cwd,
    model: state.model,
    profile_name: 'default',
    skills: [],
    tools: ['shell', 'files', 'search'],
    version: 'tui',
  }
}

function intro(state: TerminalState): Msg {
  return { id: newId(), info: sessionInfo(state), kind: 'intro', role: 'system', text: '' }
}

function sys(text: string): Msg {
  return { id: newId(), kind: 'event', role: 'system', text }
}

function panel(
  title: string,
  sections: { items?: string[]; rows?: [string, string][]; text?: string; title?: string }[],
): Msg {
  return { id: newId(), kind: 'panel', panel: { sections, title }, role: 'system', text: '' }
}

function chat(role: Msg['role'], text: string): Msg {
  return { id: newId(), kind: 'chat', role, text }
}

export function createStore(product: string) {
  const first = emptySession()
  let state: TerminalState = {
    busy: false,
    compact: false,
    completions: [],
    compIdx: 0,
    confirm: null,
    cwd: '~',
    detailsMode: 'collapsed',
    history: [],
    historyIdx: -1,
    indicator: 'kaomoji',
    input: '',
    lastTurnEndedAt: null,
    model: 'local',
    overlay: 'none',
    placeholder: '',
    product,
    queue: [],
    queueEditIdx: -1,
    selectedSessionId: first.id,
    sessions: [first],
    status: 'ready',
    statusBar: 'off',
    theme: themeForProduct(product),
    turnStartedAt: null,
    usage: { ...EMPTY_USAGE },
  }
  first.messages = [intro(state)]
  const listeners = new Set<Listener>()

  const notify = () => {
    for (const fn of listeners) fn()
  }

  const current = () => state.sessions.find((row) => row.id === state.selectedSessionId) ?? state.sessions[0]!

  const patch = (next: Partial<TerminalState>) => {
    state = { ...state, ...next }
    notify()
  }

  const setSession = (session: TerminalSession) => {
    state = {
      ...state,
      sessions: state.sessions.map((row) => (row.id === session.id ? session : row)),
    }
    notify()
  }

  const push = (msg: Msg) => {
    const session = current()
    setSession({ ...session, messages: [...session.messages, msg] })
  }

  const refreshCompletions = (input: string) => {
    const completions = filterCompletions(input, slashCatalog())
    const compIdx = Math.min(state.compIdx, Math.max(0, completions.length - 1))
    return { completions, compIdx }
  }

  const setInput = (input: string) => {
    patch({ input, ...refreshCompletions(input), historyIdx: -1 })
  }

  const closeOverlay = () => patch({ confirm: null, overlay: 'none' })

  const newSession = (note?: string, title?: string) => {
    const session = emptySession(title || 'session')
    session.messages = [intro({ ...state, selectedSessionId: session.id, sessions: [...state.sessions, session] })]
    if (note) session.messages.push(sys(note))
    patch({
      confirm: null,
      input: '',
      overlay: 'none',
      queue: [],
      selectedSessionId: session.id,
      sessions: [...state.sessions, session],
      status: 'ready',
    })
  }

  const runSlash = (raw: string): SlashResult => {
    const { arg, name } = parseSlashCommand(raw)
    const cmd = findSlashCommand(name)
    if (!cmd) return { kind: 'unknown', name }
    const session = current()

    switch (cmd.name) {
      case 'help':
        push(panel(state.theme.brand.helpHeader, slashHelpSections()))
        return { kind: 'ok' }
      case 'quit':
        push(sys(state.theme.brand.goodbye))
        return { kind: 'ok' }
      case 'clear':
        patch({
          confirm: {
            cancelLabel: 'No, keep going',
            confirmLabel: raw.startsWith('/new') ? 'Yes, start a new session' : 'Yes, clear the session',
            detail: 'This ends the current conversation and clears the transcript.',
            title: raw.startsWith('/new') ? 'Start a new session?' : 'Clear the current session?',
          },
          overlay: 'confirm',
        })
        return { kind: 'overlay', overlay: 'confirm' }
      case 'redraw':
        push(sys('ui redrawn'))
        notify()
        return { kind: 'ok' }
      case 'status':
        push(
          panel('session', [
            {
              rows: [
                ['id', session.id.slice(0, 8)],
                ['title', session.title],
                ['model', state.model],
                ['cwd', state.cwd],
                ['status', state.status],
                ['density', state.compact ? 'compact' : 'comfortable'],
                ['details', state.detailsMode],
                ['indicator', state.indicator],
              ],
            },
          ]),
        )
        return { kind: 'ok' }
      case 'title':
        if (!arg.trim()) {
          push(sys(session.title))
        } else {
          setSession({ ...session, title: arg.trim() })
          push(sys(`title → ${arg.trim()}`))
        }
        return { kind: 'ok' }
      case 'density':
        patch({ compact: !state.compact })
        push(sys(`density → ${!state.compact ? 'compact' : 'comfortable'}`))
        return { kind: 'ok' }
      case 'details': {
        const mode = arg.trim().toLowerCase()
        let next: DetailsMode = state.detailsMode
        if (mode === 'cycle' || mode === 'toggle' || mode === '') {
          next = DETAILS[(DETAILS.indexOf(state.detailsMode) + 1) % DETAILS.length]!
        } else if (DETAILS.includes(mode as DetailsMode)) {
          next = mode as DetailsMode
        } else {
          push(sys('usage: /details [hidden|collapsed|expanded|cycle]'))
          return { kind: 'ok' }
        }
        patch({ detailsMode: next })
        push(sys(`details → ${next}`))
        return { kind: 'ok' }
      }
      case 'fortune':
        push(sys(arg.trim() === 'daily' ? dailyFortune(session.id) : randomFortune()))
        return { kind: 'ok' }
      case 'copy': {
        const last = [...session.messages].reverse().find((msg) => msg.role === 'assistant' && msg.text)
        if (!last) {
          push(sys('nothing to copy'))
          return { kind: 'ok' }
        }
        void navigator.clipboard.writeText(last.text).then(
          () => push(sys('copied last assistant reply')),
          () => push(sys('clipboard unavailable')),
        )
        return { kind: 'ok' }
      }
      case 'history':
        push(
          panel('history', [
            {
              items: state.history.length ? [...state.history].reverse().slice(0, 20) : ['(empty)'],
            },
          ]),
        )
        return { kind: 'ok' }
      case 'queue':
        push(
          panel('queue', [
            {
              items: state.queue.length ? state.queue.map((item) => item.text) : ['(empty)'],
            },
          ]),
        )
        return { kind: 'ok' }
      case 'undo': {
        const msgs = [...session.messages]
        while (msgs.length && msgs[msgs.length - 1]?.role !== 'user') msgs.pop()
        if (msgs[msgs.length - 1]?.role === 'user') msgs.pop()
        const next = msgs.length ? msgs : [intro(state)]
        setSession({ ...session, messages: [...next, sys('undid last turn')] })
        return { kind: 'ok' }
      }
      case 'retry': {
        const lastUser = [...session.messages].reverse().find((msg) => msg.role === 'user')
        if (!lastUser) {
          push(sys('nothing to retry'))
          return { kind: 'ok' }
        }
        patch({ input: lastUser.text })
        return { kind: 'ok' }
      }
      case 'model':
        if (!arg.trim()) return { kind: 'overlay', overlay: 'model' }
        patch({ model: arg.trim() })
        push(sys(`model → ${arg.trim()}`))
        return { kind: 'ok' }
      case 'sessions':
        return { kind: 'overlay', overlay: 'sessions' }
      case 'tools':
        push(panel('tools', [{ items: sessionInfo(state).tools }]))
        return { kind: 'ok' }
      case 'skills':
        push(sys('no skills loaded in this browser TUI'))
        return { kind: 'ok' }
      case 'stop':
        patch({ busy: false, status: 'ready', turnStartedAt: null })
        push(sys('interrupted'))
        return { kind: 'ok' }
      case 'usage':
        push(
          panel('usage', [
            {
              rows: [
                ['input', String(state.usage.input)],
                ['output', String(state.usage.output)],
                ['total', String(state.usage.total)],
                ['context', `${state.usage.context_used}/${state.usage.context_max}`],
              ],
            },
          ]),
        )
        return { kind: 'ok' }
      case 'indicator': {
        const mode = arg.trim().toLowerCase()
        if (!mode) {
          push(sys(`indicator → ${state.indicator}`))
          return { kind: 'ok' }
        }
        if (!INDICATORS.includes(mode as IndicatorStyle)) {
          push(sys('usage: /indicator [kaomoji|emoji|ascii|unicode]'))
          return { kind: 'ok' }
        }
        patch({ indicator: mode as IndicatorStyle })
        push(sys(`indicator → ${mode}`))
        return { kind: 'ok' }
      }
      case 'statusbar': {
        const mode = arg.trim().toLowerCase()
        if (mode === 'top' || mode === 'bottom' || mode === 'off') {
          patch({ statusBar: mode })
          push(sys(`statusbar → ${mode}`))
        } else {
          push(sys('usage: /statusbar [top|bottom|off]'))
        }
        return { kind: 'ok' }
      }
      case 'prompt':
        if (!arg.trim()) {
          push(sys(`prompt → ${state.theme.brand.prompt}`))
        } else {
          patch({
            theme: { ...state.theme, brand: { ...state.theme.brand, prompt: arg.trim() } },
          })
          push(sys(`prompt → ${arg.trim()}`))
        }
        return { kind: 'ok' }
      default:
        return { kind: 'unknown', name }
    }
  }

  const submit = (text: string) => {
    const value = text.trimEnd()
    if (value.trim() === '') return
    const history = value === state.history[state.history.length - 1] ? state.history : [...state.history, value]
    patch({ completions: [], history, historyIdx: -1, input: '', queueEditIdx: -1 })

    if (looksLikeSlashCommand(value)) {
      const result = runSlash(value)
      if (result.kind === 'overlay') patch({ overlay: result.overlay })
      if (result.kind === 'unknown') push(sys(`unknown command: /${result.name} — try /help`))
      return
    }

    if (value.startsWith('!')) {
      push(chat('tool', `$ ${value.slice(1).trim()}`))
      push(sys('shell interpolation needs a connected agent backend'))
      return
    }

    if (state.busy) {
      patch({ queue: [...state.queue, { id: newId(), text: value }] })
      return
    }

    push(chat('user', value))
    const tokens = Math.min(4000, Math.ceil(value.length / 4))
    patch({
      lastTurnEndedAt: Date.now(),
      status: 'ready',
      usage: {
        ...state.usage,
        calls: state.usage.calls + 1,
        context_percent: Math.min(99, Math.round(((state.usage.context_used + tokens) / state.usage.context_max) * 100)),
        context_used: Math.min(state.usage.context_max, state.usage.context_used + tokens),
        input: state.usage.input + tokens,
        total: state.usage.total + tokens,
      },
    })
  }

  const applyShell = (shell: ShellState) => {
    const cwd = shell.cwd ?? shell.workspaces.find((row) => row.id === shell.selectedWorkspaceId)?.name ?? state.cwd
    const model = shell.model ?? state.model
    const sessions =
      shell.sessions.length === 0
        ? state.sessions
        : shell.sessions.map((row, index) => {
            const existing = state.sessions[index]
            return {
              id: row.id,
              messages: existing?.messages ?? [intro({ ...state, cwd, model })],
              startedAt: existing?.startedAt ?? Date.now(),
              title: row.title,
            }
          })
    const selectedSessionId = shell.selectedSessionId ?? sessions[0]?.id ?? state.selectedSessionId
    patch({ cwd, model, selectedSessionId, sessions })
  }

  return {
    applyShell,
    closeOverlay,
    confirmDestructive() {
      if (state.overlay !== 'confirm') return
      newSession('new session started')
    },
    current,
    faceTick() {
      return FACES
    },
    get: () => state,
    hydrate: async () => {
      try {
        applyShell(await loadShell())
      } catch {
        /* keep the local session when /api/shell is unavailable */
      }
    },
    newSession,
    patch,
    resume(id: string) {
      if (!state.sessions.some((row) => row.id === id)) return
      patch({ overlay: 'none', selectedSessionId: id })
    },
    selectCompletion(index: number) {
      const row = state.completions[index]
      if (!row) return
      const slash = state.input.indexOf('/')
      const replaceAt = slash >= 0 ? slash : 0
      const next = state.input.slice(0, replaceAt) + row.text
      setInput(next.endsWith(' ') ? next : `${next} `)
    },
    setInput,
    setThemeDark(dark: boolean) {
      const base = dark ? DARK_THEME : LIGHT_THEME
      patch({ theme: { ...base, brand: { ...base.brand, name: state.product, prompt: state.theme.brand.prompt } } })
    },
    submit,
    subscribe(fn: Listener) {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    walkHistory(dir: -1 | 1) {
      if (state.completions.length) {
        const next = (state.compIdx + dir + state.completions.length) % state.completions.length
        patch({ compIdx: next })
        return
      }
      if (state.queue.length && state.input === '') {
        const idx = state.queueEditIdx < 0 ? state.queue.length - 1 : state.queueEditIdx + dir
        if (idx < 0 || idx >= state.queue.length) return
        const item = state.queue[idx]
        if (!item) return
        patch({ input: item.text, queueEditIdx: idx })
        return
      }
      if (!state.history.length) return
      const idx = state.historyIdx < 0 ? state.history.length - 1 : state.historyIdx + dir
      if (idx < 0 || idx >= state.history.length) {
        patch({ historyIdx: -1, input: '' })
        return
      }
      patch({ historyIdx: idx, input: state.history[idx] ?? '' })
    },
  }
}

export type TerminalStore = ReturnType<typeof createStore>
