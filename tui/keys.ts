export type KeyName =
  | 'backspace'
  | 'char'
  | 'ctrl-c'
  | 'ctrl-d'
  | 'delete'
  | 'down'
  | 'end'
  | 'home'
  | 'ignore'
  | 'ctrl-v'
  | 'left'
  | 'mouse-down'
  | 'mouse-drag'
  | 'mouse-middle'
  | 'mouse-right'
  | 'mouse-up'
  | 'paste'
  | 'page down'
  | 'page up'
  | 'return'
  | 'right'
  | 'shift-tab'
  | 'shift-up'
  | 'tab'
  | 'up'
  | 'wheel-down'
  | 'wheel-up'

export type Key = {
  name: KeyName
  raw: string
  text: string
  row?: number
  column?: number
}

const escapeNames: Record<string, KeyName> = {
  '\x1b[A': 'up',
  '\x1b[B': 'down',
  '\x1b[C': 'right',
  '\x1b[D': 'left',
  '\x1b[H': 'home',
  '\x1b[F': 'end',
  '\x1b[1~': 'home',
  '\x1b[3~': 'delete',
  '\x1b[4~': 'end',
  '\x1b[5~': 'page up',
  '\x1b[6~': 'page down',
  '\x1b[Z': 'shift-tab',
  '\x1b[1;2A': 'shift-up',
  '\x1b[2;2~': 'ctrl-v'
}

const mouseName = (button: number, release: boolean): KeyName => {
  // Bits 2–4 are Shift, Alt, and Ctrl. Bit 5 is drag. 64/65 are the wheel.
  const code = button & ~0b11100
  const dragged = (code & 32) !== 0
  const wheel = code & ~32

  if (!release && (wheel === 64 || wheel === 65)) {
    return wheel === 64 ? 'wheel-up' : 'wheel-down'
  }

  if (release || (code & 3) === 3) {
    return 'mouse-up'
  }

  const buttonId = code & 3

  if (buttonId === 2 && !dragged) {
    return 'mouse-right'
  }

  if (buttonId === 1 && !dragged) {
    return 'mouse-middle'
  }

  if (buttonId !== 0) {
    return 'ignore'
  }

  return dragged ? 'mouse-drag' : 'mouse-down'
}

const mouseKey = (name: KeyName, raw: string, column: number, row: number): Key => ({
  name,
  raw,
  text: '',
  column,
  row
})

const wheelKey = (buffer: string): Key | null => {
  if (buffer.startsWith('\x1b[M')) {
    if (buffer.length < 6) {
      return null
    }

    return mouseKey(
      mouseName(buffer.charCodeAt(3) - 32, false),
      buffer.slice(0, 6),
      buffer.charCodeAt(4) - 32,
      buffer.charCodeAt(5) - 32
    )
  }

  const urxvt = /^\x1b\[(\d+);(\d+);(\d+)M/.exec(buffer)

  if (urxvt && !buffer.startsWith('\x1b[<')) {
    return mouseKey(
      mouseName(Number(urxvt[1]), false),
      urxvt[0],
      Number(urxvt[2]),
      Number(urxvt[3])
    )
  }

  if (!buffer.startsWith('\x1b[<')) {
    return null
  }

  const match = /^\x1b\[<(\d+);(\d+);(\d+)([Mm])/.exec(buffer)

  if (!match) {
    for (let index = 3; index < buffer.length && index < 32; index += 1) {
      const char = buffer[index] ?? ''

      if (char >= '@' && char <= '~') {
        return { name: 'ignore', raw: buffer.slice(0, index + 1), text: '' }
      }
    }

    return buffer.length >= 32 ? { name: 'ignore', raw: buffer.slice(0, 32), text: '' } : null
  }

  return mouseKey(
    mouseName(Number(match[1]), match[4] === 'm'),
    match[0],
    Number(match[2]),
    Number(match[3])
  )
}

export const takeKey = (buffer: string): Key | null => {
  if (!buffer) {
    return null
  }

  if (buffer[0] !== '\x1b') {
    const text = Array.from(buffer)[0] ?? ''
    return {
      name:
        text === '\r' || text === '\n' ? 'return' :
        text === '\x7f' || text === '\b' ? 'backspace' :
        text === '\x03' ? 'ctrl-c' :
        text === '\x04' ? 'ctrl-d' :
        text === '\x16' ? 'ctrl-v' :
        text === '\t' ? 'tab' :
        'char',
      raw: text,
      text
    }
  }

  if (buffer.length < 2) {
    return null
  }

  if (buffer[1] === 'O') {
    if (buffer.length < 3) {
      return null
    }

    const raw = buffer.slice(0, 3)
    return { name: escapeNames[raw] ?? 'ignore', raw, text: '' }
  }

  if (buffer[1] !== '[') {
    return { name: 'ignore', raw: buffer.slice(0, 1), text: '' }
  }

  // Bracketed paste is one key. The generic CSI scan would swallow the opener
  // and then type the pasted bytes one by one.
  if (buffer.startsWith('\x1b[200~')) {
    const end = buffer.indexOf('\x1b[201~', 6)

    if (end < 0) {
      return buffer.length > 1_048_576 ? { name: 'ignore', raw: buffer, text: '' } : null
    }

    return {
      name: 'paste',
      raw: buffer.slice(0, end + 6),
      text: buffer.slice(6, end)
    }
  }

  const wheel = wheelKey(buffer)

  if (wheel || buffer.startsWith('\x1b[<') || buffer.startsWith('\x1b[M')) {
    return wheel
  }

  for (let index = 2; index < buffer.length && index < 16; index += 1) {
    const char = buffer[index] ?? ''

    if (char < '@' || char > '~') {
      continue
    }

    const raw = buffer.slice(0, index + 1)
    return { name: escapeNames[raw] ?? 'ignore', raw, text: '' }
  }

  return buffer.length >= 16 ? { name: 'ignore', raw: buffer.slice(0, 16), text: '' } : null
}
