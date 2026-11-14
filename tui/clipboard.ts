import { spawn } from 'node:child_process'

type PipeResult = {
  ok: boolean
  out: string
}

let pending: Promise<void> = Promise.resolve()

const ignore = () => {}

const pipe = (command: string, args: string[], input?: Buffer | string): Promise<PipeResult> =>
  new Promise(resolve => {
    let settled = false
    const finish = (ok: boolean, out: string) => {
      if (settled) {
        return
      }

      settled = true
      resolve({ ok, out })
    }

    const child = spawn(command, args, {
      windowsHide: true,
      stdio: [input === undefined ? 'ignore' : 'pipe', 'pipe', 'ignore']
    })
    let out = ''

    if (!child.stdout) {
      finish(false, '')
      return
    }

    child.stdout.setEncoding('utf8')
    child.stdout.on('data', chunk => {
      out += chunk
    })
    child.on('error', () => {
      finish(false, '')
    })
    child.on('close', code => {
      finish(code === 0, out)
    })

    if (input !== undefined && child.stdin) {
      child.stdin.on('error', ignore)

      try {
        child.stdin.end(input)
      } catch {
        finish(false, '')
      }
    }
  })

const writeOsc52 = (text: string) => {
  if (!process.stdout.isTTY) {
    return
  }

  const encoded = Buffer.from(text, 'utf8').toString('base64')

  if (encoded.length > 800_000) {
    return
  }

  process.stdout.write(`\x1b]52;c;${encoded}\x07`)
}

const writeSystem = async (text: string) => {
  if (process.platform === 'win32') {
    await pipe('clip', [], Buffer.from(text, 'utf16le'))

    return
  }

  if (process.platform === 'darwin') {
    await pipe('pbcopy', [], text)

    return
  }

  if ((await pipe('wl-copy', [], text)).ok) {
    return
  }

  if ((await pipe('xclip', ['-selection', 'clipboard'], text)).ok) {
    return
  }

  await pipe('xsel', ['--clipboard', '--input'], text)
}

const readNow = async (): Promise<string> => {
  if (process.platform === 'win32') {
    const result = await pipe('powershell.exe', [
      '-NoProfile',
      '-NonInteractive',
      '-STA',
      '-Command',
      '[Console]::OutputEncoding=[Text.Encoding]::UTF8; $t=Get-Clipboard -Raw; if ($null -ne $t) {[Console]::Out.Write($t)}'
    ])

    return result.out
  }

  if (process.platform === 'darwin') {
    return (await pipe('pbpaste', [])).out
  }

  const wayland = await pipe('wl-paste', ['--no-newline'])

  if (wayland.ok) {
    return wayland.out
  }

  const xclip = await pipe('xclip', ['-selection', 'clipboard', '-o'])

  if (xclip.ok) {
    return xclip.out
  }

  return (await pipe('xsel', ['--clipboard', '--output'])).out
}

export function copyText(text: string): void {
  if (!text) {
    return
  }

  writeOsc52(text)
  pending = pending.then(() => writeSystem(text)).catch(ignore)
}

export function readText(): Promise<string> {
  return pending.then(readNow).catch(() => '')
}
