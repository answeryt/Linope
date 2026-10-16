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
  | 'up'

export type Key = {
  name: KeyName
  raw: string
  text: string
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
  '\x1b[6~': 'page down'
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
