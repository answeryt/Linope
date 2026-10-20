import { type ChildProcessWithoutNullStreams, spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { createInterface } from 'node:readline'
import { resolve } from 'node:path'

import { type DisplayEvent, parseEvent } from './events.js'

export type TerminalLink = {
  send: (text: string) => void
  stop: () => void
}

const repoRoot = () => {
  const fromLink = resolve(import.meta.dirname, '../..')

  if (existsSync(resolve(fromLink, 'kernel', 'command', '__main__.py'))) {
    return fromLink
  }

  return process.cwd()
}

const pythonCommand = () => process.env.LINOPE_PYTHON?.trim() || process.env.PYTHON?.trim() || 'python'

export function startTerminalSession(onEvent: (event: DisplayEvent) => void): TerminalLink {
  let stderr = ''
  const emitStderr = () => {
    const text = stderr.trim()

    stderr = ''

    if (text) {
      onEvent({ text, type: 'error' })
    }
  }
  const proc: ChildProcessWithoutNullStreams = spawn(
    pythonCommand(),
    ['-u', '-m', 'kernel.command', 'session'],
    {
      cwd: repoRoot(),
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUTF8: '1'
      },
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true
    }
  )

  createInterface({ input: proc.stdout }).on('line', line => {
    const event = parseEvent(line)

    if (event) {
      onEvent(event)
    } else if (line.trim()) {
      onEvent({ text: line, type: 'text' })
    }
  })
  proc.stderr.setEncoding('utf8')
  proc.stderr.on('data', chunk => {
    stderr += chunk

    if (stderr.includes('\n')) {
      emitStderr()
    }
  })
  onEvent({
    cwd: repoRoot(),
    env: '',
    store: '',
    text: '',
    type: 'session'
  })
  proc.on('close', () => {
    emitStderr()
    onEvent({ text: '离开', type: 'status' })
    onEvent({ type: 'done' })
  })

  return {
    send(text: string) {
      if (proc.exitCode !== null || proc.killed || !proc.stdin.writable) {
        onEvent({ text: '管家已经离开', type: 'error' })
        onEvent({ type: 'done' })
        return
      }

      proc.stdin.write(`${text.trim()}\n`)
    },
    stop() {
      if (proc.exitCode === null && !proc.killed) {
        try {
          proc.stdin.write('exit\n')
        } catch {
          proc.kill()
        }
      }
    }
  }
}
