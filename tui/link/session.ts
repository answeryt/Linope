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
  const child: ChildProcessWithoutNullStreams = spawn(
    pythonCommand(),
    ['-m', 'kernel.command', 'terminal', '--display', 'json'],
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
  let stderr = ''

  const emitStderr = () => {
    const text = stderr.trim()

    stderr = ''

    if (text) {
      onEvent({ text, type: 'error' })
    }
  }

  createInterface({ input: child.stdout }).on('line', line => {
    const event = parseEvent(line)

    if (event) {
      onEvent(event)
    }
  })
  child.stderr.setEncoding('utf8')
  child.stderr.on('data', chunk => {
    stderr += chunk

    if (stderr.includes('\n')) {
      emitStderr()
    }
  })
  child.on('close', () => {
    emitStderr()
    onEvent({ type: 'done' })
  })

  return {
    send(text: string) {
      child.stdin.write(`${JSON.stringify({ text, type: 'input' })}\n`)
    },
    stop() {
      child.kill()
    }
  }
}
