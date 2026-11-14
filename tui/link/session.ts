import { type ChildProcessWithoutNullStreams, spawn } from 'node:child_process'
import { createInterface } from 'node:readline'

import { type KernelEvent, parseKernelEvent } from './protocol.js'

export type TerminalLink = {
  send: (text: string) => void
  stop: () => void
}

const pythonCommand = () => process.env.LINOPE_PYTHON?.trim() || process.env.PYTHON?.trim() || 'python'

export function startTerminalSession(onEvent: (event: KernelEvent) => void): TerminalLink {
  let stderr = ''
  const emitStderr = () => {
    const text = stderr.trim()

    stderr = ''

    if (text) {
      onEvent({
        data: { message: text, source: 'stderr' },
        kind: 'diagnostic',
        seq: Number.MAX_SAFE_INTEGER,
        version: 1
      })
    }
  }
  const proc: ChildProcessWithoutNullStreams = spawn(
    pythonCommand(),
    ['-u', '-m', 'kernel.command', 'session'],
    {
      cwd: process.cwd(),
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
    if (!line.trim()) {
      return
    }
    try {
      onEvent(parseKernelEvent(line))
    } catch (error) {
      onEvent({
        data: { message: error instanceof Error ? error.message : String(error), line },
        kind: 'protocol.error',
        seq: Number.MAX_SAFE_INTEGER,
        version: 1
      })
    }
  })
  proc.stderr.setEncoding('utf8')
  proc.stderr.on('data', chunk => {
    stderr += chunk

    if (stderr.includes('\n')) {
      emitStderr()
    }
  })
  proc.on('close', () => {
    emitStderr()
    onEvent({
      data: { reason: 'process_closed' },
      kind: 'session.closed',
      seq: Number.MAX_SAFE_INTEGER,
      version: 1
    })
  })

  return {
    send(text: string) {
      if (proc.exitCode !== null || proc.killed || !proc.stdin.writable) {
        onEvent({
          data: { message: 'The clerk has left' },
          kind: 'protocol.error',
          seq: Number.MAX_SAFE_INTEGER,
          version: 1
        })
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
