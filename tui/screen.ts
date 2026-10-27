import { logoLines } from './banner.js'
import type { Focus } from './focus.js'
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
  activity: 'waiting' | 'busy'
}

export type HistoryScroll = {
  scrollY: number
  follow: boolean
}

export type HistoryLayout = {
  width: number
  historyTop: number
  historyRows: number
  contentWidth: number
  scrollbarColumn: number
  historyRow: number
}

export type ScreenState = {
  columns: number
  cwd: string
  clerk: 'here' | 'away'
  processes: LiveProcess[]
  rows: number
  scrollY?: number
  follow?: boolean
  focus?: Focus
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

const isTrimmedAway = (char: string) => char.trim().length === 0

const wrap = (text: string, width: number): string[] => {
  const limit = Math.max(1, width)
  const out: string[] = []

  for (const para of text.split(/\r?\n/)) {
    if (!para) {
      out.push('')

      continue
    }

    const chars = charsOf(para)
    let start = 0

    while (start < chars.length) {
      let used = 0
      let index = start
      let lastSpace = -1

      for (; index < chars.length; index += 1) {
        const next = charWidth(chars[index] ?? '')

        if (used + next > limit) {
          break
        }

        if (chars[index] === ' ') {
          lastSpace = index
        }

        used += next
      }

      if (index >= chars.length) {
        out.push(chars.slice(start).join(''))

        break
      }

      const cut = lastSpace > start ? lastSpace : index

      if (cut <= start) {
        out.push('')
        out.push(chars.slice(start).join(''))

        break
      }

      out.push(chars.slice(start, cut).join('').trimEnd())

      let next = cut

      while (next < chars.length && isTrimmedAway(chars[next] ?? '')) {
        next += 1
      }

      if (next >= chars.length) {
        out.push('')

        break
      }

      start = next
    }
  }

  return out.length ? out : ['']
}

export function wrapText(text: string, width: number): string[] {
  return wrap(text, width)
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

const activityWord = (raw: string): LiveProcess['activity'] | 'away' => {
  if (raw === 'working' || raw === 'busy' || raw === '在忙') {
    return 'busy'
  }

  if (raw === 'sleeping' || raw === 'waiting' || raw === '在等') {
    return 'waiting'
  }

  return 'away'
}

export function noteProcessText(current: LiveProcess[], text: string): LiveProcess[] {
  const next = current.map(item => ({ ...item }))
  const started = /^pid=(\d+)\s+capability=(\S+)/.exec(text.trim())

  if (started) {
    const id = started[1] ?? ''
    const found = next.find(item => item.id === id)

    if (found) {
      found.capability = started[2] ?? found.capability
      found.activity = 'waiting'
    } else {
      next.push({ activity: 'waiting', capability: started[2] ?? '', id })
    }

    return next
  }

  const listed = /^pid=(\d+)\s+activity=(\S+)/.exec(text.trim())

  if (listed) {
    const id = listed[1] ?? ''
    const activity = activityWord(listed[2] ?? '')

    if (activity === 'away' || text.includes('status=closed')) {
      return next.filter(item => item.id !== id)
    }

    const found = next.find(item => item.id === id)

    if (found) {
      found.activity = activity
    } else {
      next.push({ activity, capability: '', id })
    }

    return next
  }

  if (!text.trim().startsWith('{')) {
    return current
  }

  try {
    const payload = JSON.parse(text) as { facts?: { activity?: string; capability_id?: string; pid?: number | string } }
    const facts = payload.facts
    const id = facts?.pid === undefined || facts.pid === null || facts.pid === '' ? '' : String(facts.pid)

    if (!id || id === '0') {
      return current
    }

    const activity = activityWord(facts?.activity ?? '')

    if (activity === 'away') {
      return next.filter(item => item.id !== id)
    }

    const found = next.find(item => item.id === id)

    if (found) {
      found.activity = activity
      if (facts?.capability_id) {
        found.capability = facts.capability_id
      }
    } else {
      next.push({
        activity,
        capability: facts?.capability_id || '',
        id
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
    ? recent.map(item => `${item.capability} ${item.activity}`).join(', ')
    : 'none'
  const clerk = field('clerk', state.clerk, width)
  const count = field('alive', String(alive.length), width)
  const processes = field('process', names, width)
  const project = field('project', state.cwd, width)

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

const paintedTurn = (turn: Turn, contentWidth: number): string[] => {
  const prefix = turn.role === 'user' ? '❯ ' : turn.role === 'error' ? '! ' : '  '
  const color = turnColor(turn.role)
  const pad = ' '.repeat(prefix.length)
  const lines = wrap(turn.text, contentWidth - prefix.length).map((line, index) =>
    fg(color, `${index === 0 ? prefix : pad}${line}`)
  )

  lines.push('')

  return lines
}

const keptTurns = new WeakMap<Turn, { width: number; lines: string[] }>()

const linesFor = (turn: Turn, contentWidth: number): string[] => {
  if (!turn.stream) {
    const kept = keptTurns.get(turn)

    if (kept?.width === contentWidth) {
      return kept.lines
    }
  }

  const lines = paintedTurn(turn, contentWidth)

  if (!turn.stream) {
    keptTurns.set(turn, { width: contentWidth, lines })
  }

  return lines
}

let shown: {
  turns: Turn[]
  last: Turn | undefined
  tail: string | undefined
  count: number
  width: number
  lines: string[]
} | null = null

const transcript = (state: ScreenState, contentWidth: number): string[] => {
  const turns = state.turns
  const last = turns.at(-1)
  const tail = last?.text

  if (
    shown &&
    shown.turns === turns &&
    shown.last === last &&
    shown.tail === tail &&
    shown.count === turns.length &&
    shown.width === contentWidth
  ) {
    return shown.lines
  }

  const lines = turns.flatMap(turn => linesFor(turn, contentWidth))

  shown = { turns, last, tail, count: turns.length, width: contentWidth, lines }

  return lines
}

const padTo = (line: string, width: number) => {
  const gap = width - displayWidth(line)

  return gap > 0 ? `${line}${' '.repeat(gap)}` : line
}

const maxScroll = (total: number, room: number) => Math.max(0, total - Math.max(0, room))

const statusLine = (state: ScreenState, width: number) => {
  const focusLabel = state.focus === 'history' ? 'history' : 'input'
  const paused = state.follow === false ? ' │ follow paused' : ''
  const clerk = state.clerk === 'here' ? 'clerk here' : 'clerk away'
  const full = `${state.status} │ ${clerk} │ ${focusLabel}${paused} │ /help`
  const maxText = Math.max(8, width - 6)
  const text = ` ${clip(full, maxText)} `
  const fillWidth = Math.max(2, width - displayWidth(text))
  const left = Math.floor(fillWidth / 2)

  return fg(theme.border, '─'.repeat(left)) + fg(theme.text, text) + fg(theme.border, '─'.repeat(fillWidth - left))
}

export function historyLayout(state: ScreenState): HistoryLayout {
  const width = Math.max(24, state.columns - 2)
  const logoCount = logoLines(state.columns, state.rows).length
  const boxCount = panel(state, width).length
  const historyTop = logoCount + 1 + boxCount
  const historyRows = Math.max(4, state.rows - (historyTop + 2))

  return {
    width,
    historyTop,
    historyRows,
    contentWidth: Math.max(8, width - 1),
    scrollbarColumn: width,
    historyRow: historyTop + 1
  }
}

export function historyRoom(state: ScreenState): number {
  return historyLayout(state).historyRows
}

export function historyHit(layout: HistoryLayout, row: number, column: number): boolean {
  return (
    row >= layout.historyRow &&
    row < layout.historyRow + layout.historyRows &&
    column >= 1 &&
    column <= layout.scrollbarColumn
  )
}

export function transcriptRows(state: ScreenState): number {
  return transcript(state, historyLayout(state).contentWidth).length
}

export function scrollbarThumb(
  total: number,
  room: number,
  scrollY: number,
  track: number
): { start: number; size: number } | null {
  if (total <= room || track <= 0) {
    return null
  }

  const size = Math.max(1, Math.min(track, Math.round((track * room) / total)))
  const maxStart = track - size
  const maxOffset = total - room
  const clamped = Math.max(0, Math.min(scrollY, maxOffset))
  const start = maxOffset === 0 ? 0 : Math.round((maxStart * clamped) / maxOffset)

  return { start, size }
}

export function applyScroll(view: HistoryScroll, delta: number, total: number, room: number): HistoryScroll {
  const limit = maxScroll(total, room)
  const scrollY = Math.max(0, Math.min(view.scrollY + delta, limit))

  return { scrollY, follow: scrollY >= limit }
}

export function followBottom(total: number, room: number): HistoryScroll {
  return { scrollY: maxScroll(total, room), follow: true }
}

export function retainScroll(view: HistoryScroll, total: number, room: number): HistoryScroll {
  const limit = maxScroll(total, room)

  if (view.follow) {
    return { scrollY: limit, follow: true }
  }

  const scrollY = Math.max(0, Math.min(view.scrollY, limit))

  return { scrollY, follow: scrollY >= limit }
}

export function scrollLimit(state: ScreenState): number {
  const layout = historyLayout(state)

  return Math.max(0, transcript(state, layout.contentWidth).length - layout.historyRows)
}

const scrollbarCell = (index: number, thumb: { start: number; size: number } | null) => {
  if (!thumb) {
    return ' '
  }

  const onThumb = index >= thumb.start && index < thumb.start + thumb.size

  return fg(onThumb ? theme.accent : theme.muted, onThumb ? '█' : '│')
}

export function renderScreen(state: ScreenState): string {
  // Keep a 2-column right margin so terminal auto-wrap never folds a row and
  // pushes the top banner out of a short viewport. The history pane keeps one
  // more column for the scrollbar, so wrapping does not change when it appears.
  const layout = historyLayout(state)
  const logo = logoLines(state.columns, state.rows)
  const title = fg(theme.accent, 'LINOPE KERNEL')
  const box = panel(state, layout.width)
  const allHistory = transcript(state, layout.contentWidth)
  const room = layout.historyRows
  const limit = maxScroll(allHistory.length, room)
  const follow = state.follow !== false
  const scrollY = follow ? limit : Math.max(0, Math.min(state.scrollY ?? 0, limit))
  const thumb = scrollbarThumb(allHistory.length, room, scrollY, room)
  const history = Array.from({ length: room }, (_, index) => {
    const line = allHistory[scrollY + index] ?? ''

    return padTo(line, layout.contentWidth) + scrollbarCell(index, thumb)
  })
  const lines = [...logo, title, ...box, ...history, statusLine(state, layout.width)]

  return `${lines.join('\n')}\n`
}

export const helpText = [
  '/help   show these keys',
  '/clear  clear this session screen',
  '/quit   quit',
  'Tab / Shift+Tab     move focus between the input line and the history pane',
  '↑ / ↓               input: walk command history; history: scroll one line',
  'Shift+↑             scroll history up and pause following the bottom',
  '← / →               input: move the cursor',
  'Home / End          input: move the cursor; history: jump to the top or bottom',
  'PageUp / PageDown   history: one page',
  'wheel               scroll the history pane without changing focus',
  'Every other line goes to the Linope terminal, for example process list or create file.md'
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
    if (last?.role === 'assistant' && last.text === `image ${event.href}`) {
      return { status: null, turns }
    }
    return { status: null, turns: [...turns, { role: 'assistant', text: `image ${event.href}` }] }
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
