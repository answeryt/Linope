import readline from 'node:readline'

import { copyText, readText } from './clipboard.js'
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
  normalizePaste,
  recordSubmission,
  type EditorState
} from './editor.js'
import { startTerminalSession, type TerminalLink } from './link/session.js'
import { bindingFor, type Focus } from './focus.js'
import type { KernelEvent } from './link/protocol.js'
import { initialUiState, reduceKernelEvent } from './state.js'
import {
  helpText,
  historyLayout,
  renderScreen,
  transcriptRows,
  applyScroll,
  followBottom,
  retainScroll,
  scrollbarThumb,
  scrollToTrack,
  cursorIndexAt,
  displayWidth,
  highlightColumns,
  inputRow,
  stripAnsi,
  type HistoryScroll,
} from './screen.js'
import {
  drag,
  idleGesture,
  press,
  release,
  selectionText,
  spanOnRow,
  type Cell
} from './select.js'
import { fg, reset, theme } from './theme.js'
import { takeKey, type Key } from './keys.js'

let uiState = initialUiState(process.cwd())
let busy = false
let link: TerminalLink | null = null
let focus: Focus = 'input'
let view: HistoryScroll = { scrollY: 0, follow: true }
let gesture = idleGesture()
let notice = ''
let editor: EditorState = createEditor()

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
  clerk: uiState.clerk,
  columns: columns(),
  cwd: uiState.cwd,
  processes: uiState.processes,
  focus,
  rows: termRows(),
  scrollY: view.scrollY,
  follow: view.follow,
  notice,
  status: uiState.status,
  turns: uiState.turns
})

let stopping = false
let lastColumns = 0
let lastRows = 0
let resizeTimer: ReturnType<typeof setTimeout> | undefined
let drawTimer: ReturnType<typeof setTimeout> | undefined
let noticeTimer: ReturnType<typeof setTimeout> | undefined
let pasteTimer: ReturnType<typeof setTimeout> | undefined
let pastedAt = 0
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

  if (noticeTimer) {
    clearTimeout(noticeTimer)
    noticeTimer = undefined
  }

  if (pasteTimer) {
    clearTimeout(pasteTimer)
    pasteTimer = undefined
  }

  if (process.stdin.isTTY) {
    process.stdin.setRawMode(false)
  }

  link?.stop()
  if (process.stdout.isTTY) {
    process.stdout.write(`${reset}\x1b[?25h\x1b[?1000l\x1b[?1002l\x1b[?1006l\x1b[?2004l\x1b[?1049l`)
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
  const raw = renderScreen(screenState())
  const body = raw.replace(/\n$/, '').split('\n')
  const painted = `${body.map((line, index) => paintLine(index + 1, line)).join('\n')}\n`
  const frame = painted.replaceAll('\n', '\x1b[K\n')

  // Cover the previous frame from the top. Each line erases its old tail, and
  // the final erase drops rows the new frame no longer uses.
  process.stdout.write(`\x1b[H${frame}\x1b[J`)
  const prompt = fg(focus === 'history' ? theme.muted : theme.accent, PROMPT)
  process.stdout.write(paintLine(inputRow(screenState()), prompt + editor.input))

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
    uiState.turns.length = 0
    stick()
    draw()

    return
  }

  if (text === '/help') {
    uiState.turns.push({ role: 'system', text: helpText })
    stick()
    draw()

    return
  }

  uiState.turns.push({ role: 'user', text })
  stick()
  busy = true
  uiState.status = 'running'
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

const PROMPT = '❯ '

let barDrag: { offset: number } | null = null

const trackIndex = (row: number | undefined) => {
  const { layout } = metrics()

  return (row ?? 0) - layout.historyRow
}

const onBar = (key: Key) => {
  const { layout } = metrics()
  const row = key.row ?? 0
  const column = key.column ?? 0

  return (
    column >= layout.scrollbarColumn &&
    row >= layout.historyRow &&
    row < layout.historyRow + layout.historyRows
  )
}

const barColumn = (row: number) => {
  const { layout } = metrics()

  if (row < layout.historyRow || row >= layout.historyRow + layout.historyRows) {
    return 0
  }

  return layout.scrollbarColumn
}

const omitBar = (row: number, column: number) => {
  const bar = barColumn(row)

  return bar > 0 && column >= bar
}

const paintLine = (row: number, line: string) => {
  if (!gesture.mark) {
    return line
  }

  const span = spanOnRow(row, gesture.mark)

  if (!span) {
    return line
  }

  const bar = barColumn(row)
  const end = bar > 0 ? Math.min(span.end, bar - 1) : span.end

  if (span.start > end) {
    return line
  }

  return highlightColumns(line, span.start, end)
}

const plainRows = () => {
  const lines = renderScreen(screenState()).replace(/\n$/, '').split('\n').map(stripAnsi)

  lines.push(`${PROMPT}${editor.input}`)

  return lines
}

const pointerCell = (key: Key): Cell => ({
  row: Math.max(1, key.row ?? 1),
  column: Math.max(1, key.column ?? 1)
})

const showNotice = (text: string) => {
  notice = text

  if (noticeTimer) {
    clearTimeout(noticeTimer)
  }

  noticeTimer = setTimeout(() => {
    noticeTimer = undefined
    notice = ''

    if (!stopping) {
      draw()
    }
  }, 1500)
}

const clearNotice = () => {
  notice = ''

  if (noticeTimer) {
    clearTimeout(noticeTimer)
    noticeTimer = undefined
  }
}

const dropSelection = () => {
  const had = gesture.mark !== null

  gesture = idleGesture()

  if (had) {
    clearNotice()
  }

  return had
}

const placeCaret = (column: number) => {
  const at = cursorIndexAt(editor.input, column - displayWidth(PROMPT))

  focus = 'input'
  editor = moveCursor(editor, at - editor.cursor)
}

const cancelPaste = () => {
  if (pasteTimer) {
    clearTimeout(pasteTimer)
    pasteTimer = undefined
  }
}

const insertPaste = (text: string) => {
  cancelPaste()

  if (busy || stopping) {
    return
  }

  const cleaned = normalizePaste(text)

  if (!cleaned) {
    return
  }

  pastedAt = Date.now()
  gesture = idleGesture()
  clearNotice()
  focus = 'input'
  editor = insertText(editor, cleaned)
  draw()
}

const pasteClipboard = () => {
  // A right-click can also arrive as a bracketed paste in the same chunk.
  // Wait one beat, and skip the clipboard read when that paste already landed.
  if (busy || stopping || Date.now() - pastedAt < 100) {
    return
  }

  cancelPaste()
  pasteTimer = setTimeout(() => {
    pasteTimer = undefined

    if (busy || stopping) {
      return
    }

    void readText().then(text => {
      insertPaste(text)
    })
  }, 30)
}

const copyMark = () => {
  if (!gesture.mark) {
    return
  }

  const text = selectionText(plainRows(), gesture.mark, omitBar)

  if (!text) {
    gesture = { ...gesture, mark: null }

    return
  }

  copyText(text)
  showNotice('copied')
}

const placeThumb = (index: number) => {
  const { total, room } = metrics()
  const thumb = scrollbarThumb(total, room, view.scrollY, room)
  const offset = barDrag?.offset ?? Math.floor((thumb?.size ?? 1) / 2)

  view = scrollToTrack(total, room, index - offset)
}

const onTrack = (key: Key) => {
  const { total, room } = metrics()
  const index = trackIndex(key.row)
  const thumb = scrollbarThumb(total, room, view.scrollY, room)

  if (!thumb) {
    draw()

    return
  }

  if (index >= thumb.start && index < thumb.start + thumb.size) {
    barDrag = { offset: index - thumb.start }
    placeThumb(index)
    draw()

    return
  }

  barDrag = null
  view = applyScroll(view, index < thumb.start ? -room : room, total, room)
  draw()
}

const onKey = (key: Key) => {
  if (key.name === 'paste') {
    insertPaste(key.text)

    return
  }

  if (key.name === 'ctrl-v' || key.name === 'mouse-right' || key.name === 'mouse-middle') {
    gesture = { ...gesture, anchor: null, dragging: false }
    pasteClipboard()

    return
  }

  if (key.name === 'wheel-up' || key.name === 'wheel-down') {
    dropSelection()
    const { total, room } = metrics()

    barDrag = null
    view = applyScroll(view, key.name === 'wheel-up' ? -WHEEL_STEP : WHEEL_STEP, total, room)
    draw()

    return
  }

  if (key.name === 'mouse-up') {
    if (gesture.anchor) {
      gesture = drag(gesture, pointerCell(key))
    }

    const result = release(gesture)

    gesture = result.gesture
    barDrag = null

    if (result.copy) {
      copyMark()
    } else if (result.cell && result.cell.row === inputRow(screenState()) && !busy) {
      placeCaret(result.cell.column)
    }

    draw()

    return
  }

  if (key.name === 'mouse-drag') {
    if (barDrag) {
      placeThumb(trackIndex(key.row))
      draw()

      return
    }

    if (gesture.anchor) {
      gesture = drag(gesture, pointerCell(key))
      draw()
    }

    return
  }

  if (key.name === 'mouse-down') {
    if (onBar(key)) {
      dropSelection()
      onTrack(key)

      return
    }

    barDrag = null
    clearNotice()
    gesture = press(gesture, pointerCell(key), Date.now(), plainRows(), omitBar)
    draw()

    return
  }

  if (key.name === 'ignore') {
    return
  }

  const hadMark = dropSelection()
  const command = bindingFor(focus, key)

  if (command.type === 'quit') {
    shutdown(0)

    return
  }

  if (command.type === 'ctrl-d') {
    if (!editor.input) {
      shutdown(0)
    } else if (hadMark) {
      draw()
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
    if (hadMark) {
      draw()
    }

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
  process.stdout.write('\x1b[?1049h\x1b[?1000h\x1b[?1002h\x1b[?1006h\x1b[?1007l\x1b[?2004h\x1b[2J\x1b[H')
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

    gesture = { ...gesture, anchor: null, mark: null, dragging: false }
    draw()
  }, 100)
})

setWindowTitle()
link = startTerminalSession((event: KernelEvent) => {
  uiState = reduceKernelEvent(uiState, event)
  if (event.kind === 'command.completed' || event.kind === 'command.failed') {
    busy = uiState.activeTurns.size > 0
  } else if (event.kind === 'turn.started' || event.kind === 'turn.completed') {
    busy = uiState.activeTurns.size > 0
  } else if (event.kind === 'session.closed') {
    busy = false
  }

  if (!gesture.anchor && gesture.mark) {
    gesture = { ...gesture, mark: null }
  }

  if (!stopping) {
    if (event.kind === 'model.delta') {
      drawSoon()
    } else {
      draw()
    }
  }
})
draw()
