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
  | 'left'
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
  '\x1b[1;2A': 'shift-up'
}

const wheelKey = (buffer: string): Key | null => {
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

  const button = Number(match[1])
  const column = Number(match[2])
  const row = Number(match[3])
  const raw = match[0]
  // Bits 2–4 are Shift, Alt, and Ctrl. 64 is wheel up and 65 is wheel down.
  const code = button & ~0b11100

  if (match[4] === 'M' && (code === 64 || code === 65)) {
    return {
      name: code === 64 ? 'wheel-up' : 'wheel-down',
      raw,
      text: '',
      column,
      row
    }
  }

  return { name: 'ignore', raw, text: '', column, row }
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

  const wheel = wheelKey(buffer)

  if (wheel || buffer.startsWith('\x1b[<')) {
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
