import { logoLines } from './banner.js'
import type { DisplayEvent } from './link/events.js'
import { fg, fill, paint, reset, theme } from './theme.js'

export type Role = 'assistant' | 'error' | 'system' | 'user'

export type Turn = {
  role: Role
  stream?: boolean
  text: string
}

export type LiveProcess = {
  id: string
  capability: string
  activity: '在等' | '在忙'
}

export type ScreenState = {
  columns: number
  cwd: string
  clerk: '在' | '离开'
  processes: LiveProcess[]
  rows: number
  scroll?: number
  status: 'ready' | 'running'
  turns: Turn[]
}

const ANSI = /\x1b\[[0-9;]*m/g

export function displayWidth(text: string): number {
  let width = 0

  for (const char of text.replace(ANSI, '')) {
    width += charWidth(char)
  }

  return width
}

const charWidth = (char: string) => {
  const code = char.codePointAt(0) ?? 0

  if (code < 32 || (code >= 0x7f && code < 0xa0)) {
    return 0
  }

  if (
    (code >= 0x0300 && code <= 0x036f) ||
    (code >= 0x1ab0 && code <= 0x1aff) ||
    (code >= 0x1dc0 && code <= 0x1dff) ||
    (code >= 0x20d0 && code <= 0x20ff) ||
    (code >= 0xfe20 && code <= 0xfe2f)
  ) {
    return 0
  }

  if (
    code === 0x2329 ||
    code === 0x232a ||
    (code >= 0x1100 && code <= 0x115f) ||
    (code >= 0x2329 && code <= 0x232a) ||
    (code >= 0x2e80 && code <= 0xa4cf) ||
    (code >= 0xac00 && code <= 0xd7a3) ||
    (code >= 0xf900 && code <= 0xfaff) ||
    (code >= 0xfe10 && code <= 0xfe19) ||
    (code >= 0xfe30 && code <= 0xfe6f) ||
    (code >= 0xff00 && code <= 0xff60) ||
    (code >= 0xffe0 && code <= 0xffe6) ||
    (code >= 0x1f300 && code <= 0x1f64f) ||
    (code >= 0x1f900 && code <= 0x1f9ff) ||
    (code >= 0x20000 && code <= 0x3fffd)
  ) {
    return 2
  }

  return 1
}

const charsOf = (text: string) => Array.from(text)

const clip = (text: string, width: number) => {
  if (width <= 0) {
    return ''
  }

  if (displayWidth(text) <= width) {
    return text
  }

  if (width === 1) {
    return '…'
  }

  let used = 1
  let out = ''

  for (const char of charsOf(text)) {
    const next = charWidth(char)

    if (used + next > width) {
      break
    }

    out += char
    used += next
  }

  return `${out}…`
}

const takeLine = (text: string, width: number) => {
  const chars = charsOf(text)
  let used = 0
  let cut = chars.length
  let lastSpace = -1

  for (let index = 0; index < chars.length; index += 1) {
    const next = charWidth(chars[index] ?? '')

    if (used + next > width) {
      cut = index

      break
    }

    if (chars[index] === ' ') {
      lastSpace = index
    }

    used += next
  }

  if (cut < chars.length && lastSpace > 0) {
    cut = lastSpace
  }

  return {
    line: chars.slice(0, cut).join('').trimEnd(),
    rest: chars.slice(cut).join('').trimStart()
  }
}

const wrap = (text: string, width: number): string[] => {
  const out: string[] = []
  const limit = Math.max(1, width)

  for (const para of text.split(/\r?\n/)) {
    let rest = para

    if (!rest) {
      out.push('')

      continue
    }

    while (displayWidth(rest) > limit) {
      const taken = takeLine(rest, limit)

      out.push(taken.line)
      if (taken.rest === rest) {
        break
      }
      rest = taken.rest
    }

    out.push(rest)
  }

  return out.length ? out : ['']
}

const boxRow = (width: number, body: string, bodyWidth: number) => {
  const inner = Math.max(0, width - 4)
  const pad = Math.max(0, inner - bodyWidth)

  return (
    fg(theme.border, '│') +
    fill(theme.surface) +
    ' ' +
    body +
    fill(theme.surface) +
    ' '.repeat(pad) +
    ' ' +
    reset +
    fg(theme.border, '│')
  )
}

const field = (label: string, value: string, width: number) => {
  const head = label.padEnd(8)
  const shown = clip(value, Math.max(1, width - head.length))

  return {
    text: paint(theme.muted, head) + paint(theme.text, shown),
    width: displayWidth(head) + displayWidth(shown)
  }
}

const activityWord = (raw: string): LiveProcess['activity'] | '离开' => {
  if (raw === 'working' || raw === '在忙') {
    return '在忙'
  }

  if (raw === 'sleeping' || raw === '在等') {
    return '在等'
  }

  return '离开'
}

export function noteProcessText(current: LiveProcess[], text: string): LiveProcess[] {
  const next = current.map(item => ({ ...item }))
  const started = /^process_id=(\S+)\s+pid=\S+\s+capability=(\S+)/.exec(text.trim())

  if (started) {
    const id = started[1] ?? ''
    const found = next.find(item => item.id === id)

    if (found) {
      found.capability = started[2] ?? found.capability
      found.activity = '在等'
    } else {
      next.push({ activity: '在等', capability: started[2] ?? id, id })
    }

    return next
  }

  const listed = /^process_id=(\S+)\s+pid=\S+\s+activity=(\S+)/.exec(text.trim())

  if (listed) {
    const id = listed[1] ?? ''
    const activity = activityWord(listed[2] ?? '')

    if (activity === '离开' || text.includes('status=closed')) {
      return next.filter(item => item.id !== id)
    }

    const found = next.find(item => item.id === id)

    if (found) {
      found.activity = activity
    } else {
      next.push({ activity, capability: id.slice(0, 8), id })
    }

    return next
  }

  if (!text.trim().startsWith('{')) {
    return current
  }

  try {
    const payload = JSON.parse(text) as { facts?: { activity?: string; capability_id?: string; process_id?: string } }
    const facts = payload.facts

    if (!facts?.process_id) {
      return current
    }

    const activity = activityWord(facts.activity ?? '')

    if (activity === '离开') {
      return next.filter(item => item.id !== facts.process_id)
    }

    const found = next.find(item => item.id === facts.process_id)

    if (found) {
      found.activity = activity
      if (facts.capability_id) {
        found.capability = facts.capability_id
      }
    } else {
      next.push({
        activity,
        capability: facts.capability_id || facts.process_id.slice(0, 8),
        id: facts.process_id
      })
    }

    return next
  } catch {
    return current
  }
}

const infoLines = (state: ScreenState, width: number) => {
  const alive = state.processes
  const recent = alive.slice(-3)
  const names = recent.length
    ? recent.map(item => `${item.capability} ${item.activity}`).join('、')
    : '没有'
  const clerk = field('管家', state.clerk, width)
  const count = field('活着', String(alive.length), width)
  const processes = field('进程', names, width)
  const project = field('项目', state.cwd, width)

  return [clerk, count, processes, project]
}

const panel = (state: ScreenState, width: number): string[] => {
  const top = fg(theme.border, `╭${'─'.repeat(Math.max(0, width - 2))}╮`)
  const bottom = fg(theme.border, `╰${'─'.repeat(Math.max(0, width - 2))}╯`)
  const usable = Math.max(1, width - 4)
  const rows: string[] = [top]

  for (const line of infoLines(state, usable)) {
    rows.push(boxRow(width, line.text, line.width))
  }

  rows.push(bottom)

  return rows
}

const turnColor = (role: Role) => {
  if (role === 'error') {
    return theme.error
  }

  if (role === 'user') {
    return theme.text
  }

  if (role === 'system') {
    return theme.muted
  }

  return theme.accent
}

const transcript = (state: ScreenState, width: number): string[] => {
  const maxWidth = Math.max(8, width - 2)
  const lines: string[] = []

  for (const turn of state.turns) {
    const prefix = turn.role === 'user' ? '❯ ' : turn.role === 'error' ? '! ' : '  '
    const color = turnColor(turn.role)

    wrap(turn.text, maxWidth - prefix.length).forEach((line, index) => {
      const text = `${index === 0 ? prefix : ' '.repeat(prefix.length)}${line}`

      lines.push(fg(color, text))
    })
    lines.push('')
  }

  return lines
}

const statusLine = (state: ScreenState, width: number) => {
  const maxText = Math.max(8, width - 6)
  const full = `${state.status} │ ${state.clerk === '在' ? '管家在' : '管家离开'} │ /help`
  const text = ` ${clip(full, maxText)} `
  const fillWidth = Math.max(2, width - text.length)
  const left = Math.floor(fillWidth / 2)

  return fg(theme.border, '─'.repeat(left)) + fg(theme.text, text) + fg(theme.border, '─'.repeat(fillWidth - left))
}

export function historyRoom(state: ScreenState): number {
  const width = Math.max(24, state.columns - 2)
  const chrome = logoLines(state.columns, state.rows).length + 1 + panel(state, width).length + 2

  return Math.max(4, state.rows - chrome)
}

export function scrollLimit(state: ScreenState): number {
  const width = Math.max(24, state.columns - 2)

  return Math.max(0, transcript(state, width).length - historyRoom(state))
}

export function renderScreen(state: ScreenState): string {
  // Keep a 2-column right margin so terminal auto-wrap never folds a row and
  // pushes the top banner out of a short viewport.
  const width = Math.max(24, state.columns - 2)
  const logo = logoLines(state.columns, state.rows)
  const title = fg(theme.accent, 'LINOPE KERNEL')
  const box = panel(state, width)
  const allHistory = transcript(state, width)
  const room = historyRoom(state)
  const scroll = Math.min(Math.max(0, state.scroll ?? 0), Math.max(0, allHistory.length - room))
  const end = allHistory.length - scroll
  const history = allHistory.slice(Math.max(0, end - room), end)
  const lines = [...logo, title, ...box, ...history, statusLine(state, width)]

  return `${lines.join('\n')}\n`
}

export const helpText = [
  '/help   显示这些按键',
  '/clear  清空当前会话画面',
  '/quit   退出',
  '↑ / ↓               切换命令历史',
  '← / →               移动输入光标',
  'Home / End         移动光标；查看历史时回到顶部或底部',
  'PageUp / PageDown  查看更早或更新的输出',
  '其它每一行都发给 Linope 终端，例如 process list、create 文件.md'
].join('\n')

export function pushEvent(
  turns: Turn[],
  event: DisplayEvent
): { cwd?: string; session?: string; status: ScreenState['status'] | null; turns: Turn[] } {
  if (event.type === 'text') {
    const last = turns.at(-1)
    if (last?.role === 'assistant' && last.stream) {
      const next = [...turns]
      next[next.length - 1] = { role: 'assistant', text: event.text }
      return { status: null, turns: next }
    }
    if (last?.role === 'assistant' && last.text === event.text) {
      return { status: null, turns }
    }
    return { status: null, turns: [...turns, { role: 'assistant', text: event.text }] }
  }

  if (event.type === 'text-delta') {
    const next = [...turns]
    const last = next.at(-1)

    if (last?.role === 'assistant' && last.stream) {
      next[next.length - 1] = { role: 'assistant', stream: true, text: last.text + event.text }
    } else {
      next.push({ role: 'assistant', stream: true, text: event.text })
    }

    return { status: null, turns: next }
  }

  if (event.type === 'image') {
    const last = turns.at(-1)
    if (last?.role === 'assistant' && last.text === `图片 ${event.href}`) {
      return { status: null, turns }
    }
    return { status: null, turns: [...turns, { role: 'assistant', text: `图片 ${event.href}` }] }
  }

  if (event.type === 'error') {
    return { status: null, turns: [...turns, { role: 'error', text: event.text }] }
  }

  if (event.type === 'status') {
    if (event.text === 'ready' || event.text === 'running') {
      return { status: event.text, turns }
    }

    return { status: null, turns: [...turns, { role: 'system', text: event.text }] }
  }

  if (event.type === 'session') {
    const next = event.text ? [...turns, { role: 'system' as const, text: event.text }] : turns

    return {
      cwd: event.cwd,
      session: `${event.store} · ${event.env}`,
      status: null,
      turns: next
    }
  }

  return { status: 'ready', turns }
}
