import readline from 'node:readline'

import {
  backspace,
  createEditor,
  deleteForward,
  historyDown,
  historyUp,
  insertText,
  moveCursor,
  moveCursorEnd,
  moveCursorHome,
  recordSubmission,
  type EditorState
} from './editor.js'
import { startTerminalSession, type TerminalLink } from './link/session.js'
import { helpText, historyRoom, pushEvent, renderScreen, scrollLimit, displayWidth, type Turn } from './screen.js'
import { fg, reset, theme } from './theme.js'
import { takeKey, type Key } from './keys.js'

const turns: Turn[] = []
let status: 'ready' | 'running' = 'ready'
let busy = false
let link: TerminalLink | null = null
let scroll = 0
let editor: EditorState = createEditor()
let cwd = process.cwd()
let sessionName = 'linope'

const windowSize = () => {
  if (typeof process.stdout.getWindowSize === 'function') {
    return process.stdout.getWindowSize()
  }

  return [process.stdout.columns || 80, process.stdout.rows || 24] as [number, number]
}

const setWindowTitle = () => {
  if (process.stdout.isTTY) {
    process.stdout.write('\x1b]0;Linope\x07')
  }
}

const columns = () => Math.max(24, process.stdout.columns || windowSize()[0] || 80)
const termRows = () => Math.max(12, process.stdout.rows || windowSize()[1] || 24)

const screenState = () => ({
  columns: columns(),
  cwd,
  model: 'linope',
  rows: termRows(),
  scroll,
  session: sessionName,
  status,
  turns
})

let stopping = false
let lastColumns = 0
let lastRows = 0
let resizeTimer: ReturnType<typeof setTimeout> | undefined

const shutdown = (code: number) => {
  if (stopping) {
    return
  }

  stopping = true
  if (resizeTimer) {
    clearTimeout(resizeTimer)
  }

  if (process.stdin.isTTY) {
    process.stdin.setRawMode(false)
  }

  link?.stop()
  if (process.stdout.isTTY) {
    process.stdout.write(`${reset}\x1b[?25h\x1b[?1049l`)
  } else {
    process.stdout.write(`${reset}\x1b[?25h\n`)
  }
  process.exit(code)
}

const draw = () => {
  setWindowTitle()
  lastColumns = columns()
  lastRows = termRows()
  scroll = Math.min(scroll, scrollLimit(screenState()))
  const frame = renderScreen(screenState())

  // Redraw the current full-screen buffer without appending another frame.
  process.stdout.write(`\x1b[2J\x1b[H${frame}`)

  if (status !== 'ready') {
    return
  }

  if (scroll > 0) {
    process.stdout.write(fg(theme.muted, '  正在查看更早的输出，按 End 回到底部'))

    return
  }

  process.stdout.write(fg(theme.accent, '❯ ') + editor.input)
  const suffix = Array.from(editor.input).slice(editor.cursor).join('')
  const suffixWidth = displayWidth(suffix)
  if (suffixWidth > 0) {
    process.stdout.write(`\x1b[${suffixWidth}D`)
  }
}

const page = () => historyRoom(screenState())

const moveScroll = (delta: number) => {
  scroll = Math.min(scrollLimit(screenState()), Math.max(0, scroll + delta))
  draw()
}

const submit = (line: string) => {
  if (busy) {
    return
  }

  const text = line.trim()
  if (text) {
    editor = recordSubmission(editor, text)
  }
  scroll = 0

  if (!text) {
    draw()

    return
  }

  if (text === '/quit') {
    link?.send('exit')
    shutdown(0)

    return
  }

  if (text === '/clear') {
    turns.length = 0
    draw()

    return
  }

  if (text === '/help') {
    turns.push({ role: 'system', text: helpText })
    draw()

    return
  }

  turns.push({ role: 'user', text })
  busy = true
  status = 'running'
  draw()
  link?.send(text)
}

const onKey = (key: Key) => {
  if (key.name === 'ctrl-c' || (key.name === 'ctrl-d' && !editor.input)) {
    shutdown(0)

    return
  }

  if (key.name === 'page up') {
    moveScroll(page())

    return
  }

  if (key.name === 'page down') {
    moveScroll(-page())

    return
  }

  if (busy || key.name === 'ignore') {
    return
  }

  if (key.name === 'up') {
    editor = historyUp(editor)
    scroll = 0
    draw()

    return
  }

  if (key.name === 'down') {
    editor = historyDown(editor)
    scroll = 0
    draw()

    return
  }

  if (key.name === 'left') {
    editor = moveCursor(editor, -1)
    scroll = 0
    draw()

    return
  }

  if (key.name === 'right') {
    editor = moveCursor(editor, 1)
    scroll = 0
    draw()

    return
  }

  if (key.name === 'home') {
    if (scroll > 0) {
      moveScroll(scrollLimit(screenState()))
      return
    }
    editor = moveCursorHome(editor)
    scroll = 0
    draw()

    return
  }

  if (key.name === 'end') {
    if (scroll > 0) {
      scroll = 0
      draw()
      return
    }
    editor = moveCursorEnd(editor)
    scroll = 0
    draw()

    return
  }

  if (key.name === 'return') {
    submit(editor.input)

    return
  }

  if (key.name === 'backspace') {
    editor = backspace(editor)
    scroll = 0
    draw()

    return
  }

  if (key.name === 'delete') {
    editor = deleteForward(editor)
    scroll = 0
    draw()

    return
  }

  if (key.name === 'char' && key.text >= ' ') {
    editor = insertText(editor, key.text)
    scroll = 0
    draw()
  }
}

let pendingInput = ''

const onData = (chunk: string) => {
  pendingInput += chunk

  while (pendingInput) {
    const key = takeKey(pendingInput)

    if (!key) {
      return
    }

    pendingInput = pendingInput.slice(key.raw.length)
    onKey(key)
  }
}

if (process.stdin.isTTY) {
  process.stdout.write('\x1b[?1049h\x1b[2J\x1b[H')
  readline.emitKeypressEvents(process.stdin)
  process.stdin.setRawMode(true)
  process.stdin.setEncoding('utf8')
  process.stdin.on('data', onData)
} else {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
  })

  rl.on('line', submit)
  rl.on('close', () => {
    shutdown(0)
  })
}
process.on('SIGINT', () => {
  shutdown(0)
})
process.stdout.on('resize', () => {
  if (resizeTimer) {
    clearTimeout(resizeTimer)
  }

  resizeTimer = setTimeout(() => {
    resizeTimer = undefined
    const nextColumns = columns()
    const nextRows = termRows()

    if (nextColumns === lastColumns && nextRows === lastRows) {
      return
    }

    draw()
  }, 100)
})

link = startTerminalSession(event => {
  const next = pushEvent(turns, event)

  turns.splice(0, turns.length, ...next.turns)

  if (next.cwd) {
    cwd = next.cwd
  }

  if (next.session) {
    sessionName = next.session
  }

  if (next.status) {
    status = next.status
  }

  if (event.type === 'done') {
    busy = false
  }

  if (!stopping) {
    draw()
  }
})
draw()
