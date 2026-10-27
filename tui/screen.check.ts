import assert from 'node:assert/strict'

import { parseEvent } from './link/events.ts'
import {
  applyScroll,
  displayWidth,
  followBottom,
  historyHit,
  historyLayout,
  noteProcessText,
  pushEvent,
  renderScreen,
  retainScroll,
  scrollbarThumb,
  wrapText,
  type Turn
} from './screen.ts'

const wide = displayWidth('一致性')
assert.equal(wide, 6)

const turns: Turn[] = [
  { role: 'user', text: '旧命令' },
  { role: 'assistant', text: `开始${'中'.repeat(400)}结束` }
]
const state = {
  clerk: 'here' as const,
  columns: 30,
  cwd: 'D:/other/Linope',
  processes: [{ activity: 'waiting' as const, capability: 'tools.bash', id: 'abc' }],
  rows: 16,
  status: 'ready' as const,
  turns
}

const bottom = renderScreen({ ...state, follow: true })
const top = renderScreen({ ...state, follow: false, scrollY: 0 })
const topLayout = historyLayout({ ...state, follow: false, scrollY: 0 })
const topLines = top.split('\n').slice(topLayout.historyTop, topLayout.historyTop + topLayout.historyRows)
const bottomLines = bottom.split('\n').slice(topLayout.historyTop, topLayout.historyTop + topLayout.historyRows)
assert.equal(bottom.includes('结束'), true)
assert.equal(bottom.includes('旧命令'), false)
assert.equal(top.includes('旧命令'), true)
assert.equal(top.includes('结束'), false)
assert.equal(bottom.includes('\x1b[3J'), false)
assert.equal(topLines.some(line => line.includes('█')), true)
assert.ok(topLines.every(line => displayWidth(line) === topLayout.width))
assert.equal(bottomLines.some(line => line.includes('█')), true)

const fitted = renderScreen({
  ...state,
  columns: 30,
  follow: true,
  rows: 24,
  turns: [{ role: 'user', text: 'hi' }]
})
const fittedLayout = historyLayout({ ...state, columns: 30, rows: 24 })
const fittedLines = fitted.split('\n').slice(fittedLayout.historyTop, fittedLayout.historyTop + fittedLayout.historyRows)
assert.equal(fitted.includes('hi'), true)
assert.equal(fittedLines.some(line => line.includes('█')), false)

const paused = renderScreen({ ...state, columns: 80, follow: false, focus: 'history', scrollY: 0 })
assert.equal(paused.split('\n').at(-2)?.includes('follow paused'), true)
assert.equal(paused.split('\n').at(-2)?.includes('history'), true)
assert.equal(historyHit(topLayout, topLayout.historyRow, 1), true)
assert.equal(historyHit(topLayout, topLayout.historyRow - 1, 1), false)
assert.equal(historyHit(topLayout, topLayout.historyRow, topLayout.scrollbarColumn + 1), false)

const pausedView = retainScroll({ scrollY: 4, follow: false }, 40, 10)
assert.deepEqual(pausedView, { scrollY: 4, follow: false })
assert.deepEqual(retainScroll({ scrollY: 4, follow: true }, 40, 10), followBottom(40, 10))
const lifted = applyScroll({ scrollY: 10, follow: true }, -1, 30, 10)
assert.equal(lifted.follow, false)
assert.equal(lifted.scrollY, 9)
assert.deepEqual(applyScroll(lifted, 100, 30, 10), { scrollY: 20, follow: true })
assert.deepEqual(scrollbarThumb(5, 10, 0, 10), null)
assert.ok(scrollbarThumb(30, 10, 0, 10))

let streamed = pushEvent([], { type: 'text-delta', text: '第一段' }).turns
streamed = pushEvent(streamed, { type: 'text-delta', text: '第二段' }).turns
streamed = pushEvent(streamed, { type: 'text', text: '第一段第二段' }).turns
assert.deepEqual(streamed, [{ role: 'assistant', text: '第一段第二段' }])
assert.equal(pushEvent(streamed, { type: 'text', text: '第一段第二段' }).turns, streamed)

const session = parseEvent(
  JSON.stringify({
    type: 'session',
    cwd: 'D:/other/Linope',
    store: 'file:.linope/resources.json',
    env: '已配置',
    text: ''
  })
)
assert.equal(session?.type, 'session')

const noted = noteProcessText(
  [],
  'pid=50040 capability=tools.bash'
)
assert.equal(noted[0]?.id, '50040')
assert.equal(noted[0]?.capability, 'tools.bash')
assert.equal(noted[0]?.activity, 'waiting')
const listed = noteProcessText(noted, 'pid=50040 activity=working status=ready')
assert.equal(listed[0]?.activity, 'busy')
assert.equal(renderScreen({ ...state, columns: 80 }).includes('clerk'), true)
assert.equal(renderScreen({ ...state, columns: 80 }).includes('tools.bash waiting'), true)

const longText = `${'alpha bravo charlie delta '.repeat(40)}\n${'中文折行'.repeat(80)}\n\n结尾`
const firstLines = wrapText(longText, 24)
const secondLines = wrapText(longText, 24)
assert.deepEqual(secondLines, firstLines)
assert.equal(firstLines.at(-1), '结尾')
assert.equal(firstLines.includes(''), true)
assert.equal(firstLines.some(line => line.startsWith('alpha bravo')), true)
assert.ok(firstLines.every(line => line === '' || displayWidth(line) <= 24))

const painted = renderScreen({
  ...state,
  columns: 40,
  rows: 48,
  turns: [{ role: 'assistant', text: longText }]
})
const paintedAgain = renderScreen({
  ...state,
  columns: 40,
  rows: 48,
  turns: [{ role: 'assistant', text: longText }]
})
assert.equal(paintedAgain, painted)
assert.equal(painted.includes('结尾'), true)

const live: Turn = { role: 'assistant', stream: true, text: 'ab' }
const early = renderScreen({ ...state, columns: 40, rows: 48, turns: [live] })
live.text = `${'中'.repeat(80)}结束`
const later = renderScreen({ ...state, columns: 40, rows: 48, turns: [live] })
assert.equal(later.includes('结束'), true)
assert.notEqual(later, early)

console.log('tui screen checks passed')
