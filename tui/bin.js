#!/usr/bin/env node
import { spawn } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const separator = process.platform === 'win32' ? ';' : ':'
const current = process.env.PYTHONPATH?.trim()
const pythonPath = current ? `${root}${separator}${current}` : root
const child = spawn(process.env.LINOPE_PYTHON?.trim() || process.env.PYTHON?.trim() || 'python', ['-m', 'tui.launch', ...process.argv.slice(2)], {
  cwd: process.cwd(),
  env: {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',
    PYTHONPATH: pythonPath,
    PYTHONUTF8: '1'
  },
  stdio: 'inherit',
  windowsHide: false
})

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
    return
  }

  process.exit(code ?? 1)
})
child.on('error', error => {
  process.stderr.write(`${error.message}\n`)
  process.exit(1)
})
