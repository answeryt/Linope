import assert from 'node:assert/strict'

import {
  columnCells,
  cursorIndexAt,
  displayWidth,
  highlightColumns,
  historyLayout,
  inputRow,
  renderScreen,
  stripAnsi
} from './screen.ts'
import { fg, theme } from './theme.ts'
import {
  drag,
  idleGesture,
  lineMark,
  press,
  release,
  selectionText,
  wordMark,
  type TextMark
} from './select.ts'

assert.equal(cursorIndexAt('hello', 1), 0)
assert.equal(cursorIndexAt('hello', 2), 1)
assert.equal(cursorIndexAt('hello', 20), 5)
assert.equal(cursorIndexAt('你好', 1), 0)
assert.equal(cursorIndexAt('你好', 2), 1)
assert.equal(cursorIndexAt('你好', 3), 1)
assert.equal(cursorIndexAt('你好', 4), 2)

const colored = fg(theme.text, '你好')
const marked = highlightColumns(colored, 1, 2)
assert.equal(displayWidth(marked), displayWidth(colored))
assert.equal(stripAnsi(marked), '你好')
assert.equal(marked.includes('\x1b[7m'), true)

const rows = ['alpha  beta', '第二行', '  hello█']
const omitBar = (row: number, column: number) => row === 3 && column >= 8
assert.equal(
  selectionText(rows, { anchor: { row: 1, column: 8 }, head: { row: 2, column: 2 } }),
  'beta\n第'
)
assert.equal(
  selectionText(rows, { anchor: { row: 2, column: 4 }, head: { row: 1, column: 1 } }),
  'alpha  beta\n第二'
)
assert.equal(selectionText(rows, { anchor: { row: 3, column: 1 }, head: { row: 3, column: 12 } }, omitBar), '  hello')

const word = wordMark(rows, { row: 1, column: 8 })
assert.ok(word)
assert.equal(selectionText(rows, word as TextMark), 'beta')
const line = lineMark(rows, { row: 3, column: 3 }, omitBar)
assert.ok(line)
assert.equal(selectionText(rows, line as TextMark, omitBar), '  hello')
assert.equal(wordMark(rows, { row: 1, column: 6 }), null)

let gesture = idleGesture()
gesture = press(gesture, { row: 1, column: 1 }, 0, rows)
gesture = drag(gesture, { row: 1, column: 5 })
const dragged = release(gesture)
assert.equal(dragged.copy, true)
assert.equal(selectionText(rows, dragged.gesture.mark as TextMark), 'alpha')

gesture = press(idleGesture(), { row: 1, column: 1 }, 0, rows)
const clicked = release(gesture)
assert.equal(clicked.copy, false)
assert.deepEqual(clicked.cell, { row: 1, column: 1 })

gesture = press(clicked.gesture, { row: 1, column: 1 }, 200, rows)
assert.equal(selectionText(rows, gesture.mark as TextMark), 'alpha')
const wordRelease = release(gesture)
assert.equal(wordRelease.copy, true)
gesture = press(wordRelease.gesture, { row: 1, column: 1 }, 300, rows)
assert.equal(selectionText(rows, gesture.mark as TextMark), 'alpha  beta')
gesture = press(gesture, { row: 1, column: 3 }, 1000, rows)
assert.equal(gesture.mark, null)

const state = {
  clerk: 'here' as const,
  columns: 100,
  cwd: 'C:/Users/86182/project',
  follow: true,
  processes: [],
  rows: 28,
  status: 'ready' as const,
  turns: [
    { role: 'user' as const, text: 'hello clipboard' },
    { role: 'assistant' as const, text: `${'中'.repeat(400)}结束` }
  ]
}
const frame = renderScreen(state)
const frameRows = frame.replace(/\n$/, '').split('\n')
assert.equal(frameRows.length + 1, inputRow(state))
const plain = frameRows.map(line => stripAnsi(line))
const hit = plain.findIndex(line => line.includes('hello clipboard'))
assert.ok(hit >= 0)
const hello = columnCells(plain[hit] ?? '').find(cell => cell.char === 'h' && plain[hit]?.slice(cell.column - 1).startsWith('hello'))
assert.ok(hello)
const copied = selectionText(plain, {
  anchor: { row: hit + 1, column: hello.column },
  head: { row: hit + 1, column: hello.column + 'hello clipboard'.length - 1 }
})
assert.equal(copied, 'hello clipboard')
const tight = {
  ...state,
  columns: 30,
  rows: 16,
  turns: [{ role: 'assistant' as const, text: `开始${'中'.repeat(400)}结束` }]
}
const tightFrame = renderScreen(tight).replace(/\n$/, '').split('\n').map(line => stripAnsi(line))
const tightLayout = historyLayout(tight)
const barRow = tightFrame.findIndex((line, index) => index + 1 >= tightLayout.historyRow && line.includes('█'))
assert.ok(barRow >= 0)
const barred = selectionText(
  tightFrame,
  { anchor: { row: barRow + 1, column: 1 }, head: { row: barRow + 1, column: tightLayout.scrollbarColumn } },
  (row, column) => row >= tightLayout.historyRow && column >= tightLayout.scrollbarColumn
)
assert.equal(barred.includes('█'), false)
assert.equal(barred.includes('│'), false)
assert.equal(renderScreen({ ...state, notice: 'copied' }).includes('copied'), true)

console.log('tui select checks passed')
