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
import { bindingFor, type Focus } from './focus.js'
import {
  helpText,
  historyHit,
  historyLayout,
  noteProcessText,
  pushEvent,
  renderScreen,
  transcriptRows,
  applyScroll,
  followBottom,
  retainScroll,
  displayWidth,
  type HistoryScroll,
  type LiveProcess,
  type Turn
} from './screen.js'
import { fg, reset, theme } from './theme.js'
import { takeKey, type Key } from './keys.js'

const turns: Turn[] = []
let status: 'ready' | 'running' = 'ready'
let busy = false
let link: TerminalLink | null = null
let focus: Focus = 'input'
let view: HistoryScroll = { scrollY: 0, follow: true }
let editor: EditorState = createEditor()
let cwd = process.cwd()
let clerk: 'here' | 'away' = 'here'
let processes: LiveProcess[] = []

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
  clerk,
  columns: columns(),
  cwd,
  processes,
  focus,
  rows: termRows(),
  scrollY: view.scrollY,
  follow: view.follow,
  status,
  turns
})

let stopping = false
let lastColumns = 0
let lastRows = 0
let resizeTimer: ReturnType<typeof setTimeout> | undefined
let drawTimer: ReturnType<typeof setTimeout> | undefined
const DRAW_WAIT_MS = 30

const shutdown = (code: number) => {
  if (stopping) {
    return
  }

  stopping = true
  if (resizeTimer) {
    clearTimeout(resizeTimer)
  }
  if (drawTimer) {
    clearTimeout(drawTimer)
    drawTimer = undefined
  }

  if (process.stdin.isTTY) {
    process.stdin.setRawMode(false)
  }

  link?.stop()
  if (process.stdout.isTTY) {
    process.stdout.write(`${reset}\x1b[?25h\x1b[?1000l\x1b[?1006l\x1b[?1049l`)
  } else {
    process.stdout.write(`${reset}\x1b[?25h\n`)
  }
  process.exit(code)
}

const draw = () => {
  if (drawTimer) {
    clearTimeout(drawTimer)
    drawTimer = undefined
  }

  lastColumns = columns()
  lastRows = termRows()
  const { total, room } = metrics()
  view = retainScroll(view, total, room)
  const frame = renderScreen(screenState()).replaceAll('\n', '\x1b[K\n')

  // Cover the previous frame from the top. Each line erases its old tail, and
  // the final erase drops rows the new frame no longer uses.
  process.stdout.write(`\x1b[H${frame}\x1b[J`)
  process.stdout.write(fg(focus === 'history' ? theme.muted : theme.accent, '❯ ') + editor.input)

  if (focus === 'history') {
    process.stdout.write('\x1b[?25l')

    return
  }

  process.stdout.write('\x1b[?25h')
  const suffix = Array.from(editor.input).slice(editor.cursor).join('')
  const suffixWidth = displayWidth(suffix)
  if (suffixWidth > 0) {
    process.stdout.write(`\x1b[${suffixWidth}D`)
  }
}

const drawSoon = () => {
  if (drawTimer) {
    return
  }

  drawTimer = setTimeout(() => {
    drawTimer = undefined
    if (!stopping) {
      draw()
    }
  }, DRAW_WAIT_MS)
}

const WHEEL_STEP = 3

const metrics = () => {
  const layout = historyLayout(screenState())

  return { layout, total: transcriptRows(screenState()), room: layout.historyRows }
}

const stick = () => {
  const { total, room } = metrics()
  view = followBottom(total, room)
}

const submit = (line: string) => {
  if (busy) {
    return
  }

  const text = line.trim()
  if (text) {
    editor = recordSubmission(editor, text)
  }

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
    stick()
    draw()

    return
  }

  if (text === '/help') {
    turns.push({ role: 'system', text: helpText })
    stick()
    draw()

    return
  }

  turns.push({ role: 'user', text })
  stick()
  busy = true
  status = 'running'
  draw()
  link?.send(text)
}

const edit = (key: Key) => {
  if (key.name === 'up') {
    editor = historyUp(editor)

    return
  }

  if (key.name === 'down') {
    editor = historyDown(editor)

    return
  }

  if (key.name === 'left') {
    editor = moveCursor(editor, -1)

    return
  }

  if (key.name === 'right') {
    editor = moveCursor(editor, 1)

    return
  }

  if (key.name === 'home') {
    editor = moveCursorHome(editor)

    return
  }

  if (key.name === 'end') {
    editor = moveCursorEnd(editor)

    return
  }

  if (key.name === 'backspace') {
    editor = backspace(editor)

    return
  }

  if (key.name === 'delete') {
    editor = deleteForward(editor)

    return
  }

  if (key.name === 'char' && key.text >= ' ') {
    editor = insertText(editor, key.text)
  }
}

const onKey = (key: Key) => {
  if (key.name === 'wheel-up' || key.name === 'wheel-down') {
    const { layout, total, room } = metrics()

    if (!historyHit(layout, key.row ?? 0, key.column ?? 0)) {
      return
    }

    view = applyScroll(view, key.name === 'wheel-up' ? -WHEEL_STEP : WHEEL_STEP, total, room)
    draw()

    return
  }

  const command = bindingFor(focus, key)

  if (command.type === 'quit') {
    shutdown(0)

    return
  }

  if (command.type === 'ctrl-d') {
    if (!editor.input) {
      shutdown(0)
    }

    return
  }

  if (command.type === 'focus') {
    focus = command.focus
    draw()

    return
  }

  if (command.type === 'scroll' || command.type === 'scroll-page' || command.type === 'scroll-edge') {
    const { total, room } = metrics()

    if (command.type === 'scroll') {
      view = applyScroll(view, command.delta, total, room)
    } else if (command.type === 'scroll-page') {
      view = applyScroll(view, command.direction * room, total, room)
    } else if (command.edge === 'top') {
      view = retainScroll({ scrollY: 0, follow: false }, total, room)
    } else {
      view = followBottom(total, room)
    }

    draw()

    return
  }

  if (busy || (command.type !== 'editor' && command.type !== 'submit')) {
    return
  }

  if (command.type === 'submit') {
    submit(editor.input)

    return
  }

  edit(command.key)
  draw()
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
  process.stdout.write('\x1b[?1049h\x1b[?1000h\x1b[?1006h\x1b[2J\x1b[H')
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

setWindowTitle()
link = startTerminalSession(event => {
  const next = pushEvent(turns, event)

  turns.splice(0, turns.length, ...next.turns)

  if (next.cwd) {
    cwd = next.cwd
  }

  if (event.type === 'text') {
    processes = noteProcessText(processes, event.text)
  }

  if (event.type === 'status' && event.text === 'left') {
    clerk = 'away'
    processes = []
  }

  if (next.status) {
    status = next.status
  }

  if (event.type === 'done') {
    busy = false
  }

  if (!stopping) {
    if (event.type === 'text-delta') {
      drawSoon()
    } else {
      draw()
    }
  }
})
draw()
