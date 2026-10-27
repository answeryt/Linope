import {
  backspace,
  createEditor,
  deleteForward,
  historyDown,
  historyUp,
  insertText,
  moveCursor,
  recordSubmission
} from './editor.ts'
import { takeKey } from './keys.ts'

const equal = (actual: unknown, expected: unknown) => {
  if (actual !== expected) {
    throw new Error(`expected ${String(expected)}, received ${String(actual)}`)
  }
}

const deepEqual = (actual: unknown, expected: unknown) => {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`)
  }
}

let editor = createEditor()
editor = insertText(editor, 'process list')
equal(editor.input, 'process list')
equal(editor.cursor, 12)

editor = moveCursor(editor, -4)
editor = insertText(editor, 'status ')
equal(editor.input, 'process status list')
equal(editor.cursor, 15)

editor = backspace(editor)
equal(editor.input, 'process statuslist')
editor = deleteForward(editor)
equal(editor.input, 'process statusist')

editor = recordSubmission(editor, 'process statusist')
editor = recordSubmission(editor, 'process status')
editor = recordSubmission(editor, 'process status')
editor = historyUp(editor)
equal(editor.input, 'process status')
editor = historyUp(editor)
equal(editor.input, 'process statusist')
editor = historyDown(editor)
equal(editor.input, 'process status')
editor = historyDown(editor)
equal(editor.input, '')

equal(takeKey('\x1b[A')?.name, 'up')
equal(takeKey('\x1b[B')?.name, 'down')
equal(takeKey('\x1b[C')?.name, 'right')
equal(takeKey('\x1b[D')?.name, 'left')
equal(takeKey('\x1b[3~')?.name, 'delete')
equal(takeKey('\t')?.name, 'tab')
equal(takeKey('\x1b[Z')?.name, 'shift-tab')
equal(takeKey('\x1b[1;2A')?.name, 'shift-up')
deepEqual(takeKey('\x1b[<64;12;5M'), { name: 'wheel-up', raw: '\x1b[<64;12;5M', text: '', column: 12, row: 5 })
deepEqual(takeKey('\x1b[<65;3;9M'), { name: 'wheel-down', raw: '\x1b[<65;3;9M', text: '', column: 3, row: 9 })
deepEqual(takeKey('\x1b[<68;2;4M'), { name: 'wheel-up', raw: '\x1b[<68;2;4M', text: '', column: 2, row: 4 })
deepEqual(takeKey('🙂'), { name: 'char', raw: '🙂', text: '🙂' })

console.log('tui editor checks passed')
