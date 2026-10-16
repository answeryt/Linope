import assert from 'node:assert/strict'

import { parseEvent } from './link/events.ts'
import { displayWidth, pushEvent, renderScreen, type Turn } from './screen.ts'

const wide = displayWidth('一致性')
assert.equal(wide, 6)

const turns: Turn[] = [
  { role: 'user', text: '旧命令' },
  { role: 'assistant', text: `开始${'中'.repeat(400)}结束` }
]
const state = {
  columns: 30,
  cwd: 'D:/other/Linope',
  model: 'linope',
  rows: 16,
  session: 'file:.linope/resources.json · 已配置',
  status: 'ready' as const,
  turns
}

const bottom = renderScreen({ ...state, scroll: 0 })
const top = renderScreen({ ...state, scroll: 1000 })
assert.equal(bottom.includes('结束'), true)
assert.equal(bottom.includes('旧命令'), false)
assert.equal(top.includes('旧命令'), true)
assert.equal(top.includes('结束'), false)
assert.equal(bottom.includes('\x1b[3J'), false)

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

console.log('tui screen checks passed')
