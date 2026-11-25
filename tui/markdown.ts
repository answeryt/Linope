import { paint, theme } from './theme.js'

type Marks = {
  bold: boolean
  italic: boolean
  underline: boolean
  code: boolean
}

const plain = (): Marks => ({ bold: false, italic: false, underline: false, code: false })

const RULE = /^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})[ \t]*$/
const HEADING = /^ {0,3}(#{1,6})(?:[ \t]+(.*))?$/
const FENCE = /^ {0,3}(`{3,}|~{3,})/

const isWord = (char: string | undefined) => char !== undefined && /[A-Za-z0-9]/.test(char)

const canOpen = (source: string, index: number, marker: string) => {
  const after = source[index + marker.length]

  if (after === undefined || after === ' ' || after === '\t') {
    return false
  }

  if (marker[0] === '_' && isWord(source[index - 1])) {
    return false
  }

  return true
}

const findCloser = (source: string, marker: string, from: number) => {
  for (let index = from; index <= source.length - marker.length; index += 1) {
    if (!source.startsWith(marker, index)) {
      continue
    }

    const before = source[index - 1]

    if (before === ' ' || before === '\t') {
      continue
    }

    if (marker[0] === '_' && isWord(source[index + marker.length])) {
      continue
    }

    return index
  }

  return -1
}

const takeMarker = (source: string, index: number) => {
  const candidates = ['***', '___', '**', '__', '*', '_']

  for (const marker of candidates) {
    if (!source.startsWith(marker, index) || !canOpen(source, index, marker)) {
      continue
    }

    const closer = findCloser(source, marker, index + marker.length)

    if (closer > index + marker.length) {
      return { marker, closer }
    }
  }

  return null
}

const withMarker = (base: Marks, marker: string): Marks => ({
  bold: base.bold || marker.length !== 1,
  italic: base.italic || marker.length !== 2,
  underline: base.underline,
  code: base.code
})

const styled = (text: string, marks: Marks, base: Marks, restore: string) => {
  let open = ''
  let close = ''

  if (marks.code && !base.code) {
    open += paint(theme.muted)
    close = paint(restore) + close
  }

  if (marks.bold && !base.bold) {
    open += '\x1b[1m'
    close = `\x1b[22m${close}`
  }

  if (marks.italic && !base.italic) {
    open += '\x1b[3m'
    close = `\x1b[23m${close}`
  }

  if (marks.underline && !base.underline) {
    open += '\x1b[4m'
    close = `\x1b[24m${close}`
  }

  if (!open) {
    return text
  }

  return open + text + close
}

const inline = (source: string, base: Marks, restore: string): string => {
  let out = ''
  let index = 0

  while (index < source.length) {
    if (source.startsWith('`', index)) {
      const end = source.indexOf('`', index + 1)

      if (end > index + 1) {
        out += styled(source.slice(index + 1, end), { ...base, code: true }, base, restore)
        index = end + 1

        continue
      }
    }

    const taken = takeMarker(source, index)

    if (taken) {
      const marks = withMarker(base, taken.marker)
      const inner = inline(source.slice(index + taken.marker.length, taken.closer), marks, restore)

      out += styled(inner, marks, base, restore)
      index = taken.closer + taken.marker.length

      continue
    }

    out += source[index]
    index += 1
  }

  return out
}

const headingMarks = (level: number): Marks => ({
  bold: true,
  italic: false,
  underline: level === 1,
  code: false
})

const renderLine = (line: string, width: number, restore: string) => {
  if (RULE.test(line)) {
    return '─'.repeat(Math.min(Math.max(width, 0), 80))
  }

  const heading = HEADING.exec(line)

  if (!heading) {
    return inline(line, plain(), restore)
  }

  const level = heading[1]?.length ?? 1
  const content = (heading[2] ?? '').replace(/[ \t]+#+\s*$/, '')
  const marks = headingMarks(level)
  const body = inline(content, marks, restore)
  const shown = level >= 3 ? `${'#'.repeat(level)} ${body}` : body

  return styled(shown, marks, plain(), restore)
}

export function renderMarkdown(text: string, width: number, restore: string): string {
  const lines = text.split(/\r?\n/)
  const out: string[] = []
  let fence: { char: string; length: number } | null = null

  for (const line of lines) {
    const opened = FENCE.exec(line)

    if (fence) {
      out.push(line)

      if (opened && opened[1]?.[0] === fence.char && (opened[1]?.length ?? 0) >= fence.length) {
        fence = null
      }

      continue
    }

    if (opened?.[1]) {
      fence = { char: opened[1][0] ?? '`', length: opened[1].length }
      out.push(line)

      continue
    }

    out.push(renderLine(line, width, restore))
  }

  return out.join('\n')
}
