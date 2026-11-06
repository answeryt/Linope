import { columnCells } from './screen.js'

export type Cell = {
  row: number
  column: number
}

export type TextMark = {
  anchor: Cell
  head: Cell
}

export type Gesture = {
  anchor: Cell | null
  mark: TextMark | null
  presses: number
  pressedAt: number
  pressed: Cell | null
  dragging: boolean
}

export const CLICK_MS = 400

const isSpace = (char: string) => char.trim().length === 0

export const idleGesture = (): Gesture => ({
  anchor: null,
  mark: null,
  presses: 0,
  pressedAt: 0,
  pressed: null,
  dragging: false
})

export const sameCell = (left: Cell, right: Cell) =>
  left.row === right.row && left.column === right.column

export const orderMark = (mark: TextMark): { start: Cell; end: Cell } => {
  const { anchor, head } = mark

  if (anchor.row < head.row || (anchor.row === head.row && anchor.column <= head.column)) {
    return { start: anchor, end: head }
  }

  return { start: head, end: anchor }
}

export const spanOnRow = (row: number, mark: TextMark): { start: number; end: number } | null => {
  const { start, end } = orderMark(mark)

  if (row < start.row || row > end.row) {
    return null
  }

  return {
    start: row === start.row ? start.column : 1,
    end: row === end.row ? end.column : Number.MAX_SAFE_INTEGER
  }
}

const cellsOn = (
  line: string,
  row: number,
  omit?: (row: number, column: number) => boolean
) => columnCells(line).filter(cell => !omit?.(row, cell.column))

export function selectionText(
  rows: string[],
  mark: TextMark,
  omit?: (row: number, column: number) => boolean
): string {
  const { start, end } = orderMark(mark)
  const parts: string[] = []

  for (let row = start.row; row <= end.row; row += 1) {
    const from = row === start.row ? start.column : 1
    const to = row === end.row ? end.column : Number.MAX_SAFE_INTEGER
    let piece = ''

    for (const cell of cellsOn(rows[row - 1] ?? '', row, omit)) {
      const last = cell.column + cell.width - 1

      if (last < from || cell.column > to) {
        continue
      }

      piece += cell.char
    }

    parts.push(piece.replace(/[ \t]+$/g, ''))
  }

  while (parts.length > 0 && parts[parts.length - 1] === '') {
    parts.pop()
  }

  return parts.join('\n')
}

const markBetween = (row: number, first: { column: number }, last: { column: number; width: number }): TextMark => ({
  anchor: { row, column: first.column },
  head: { row, column: last.column + last.width - 1 }
})

export function wordMark(
  rows: string[],
  cell: Cell,
  omit?: (row: number, column: number) => boolean
): TextMark | null {
  const cells = cellsOn(rows[cell.row - 1] ?? '', cell.row, omit)
  const hit = cells.findIndex(item => cell.column >= item.column && cell.column < item.column + item.width)

  if (hit < 0 || isSpace(cells[hit]?.char ?? '')) {
    return null
  }

  let start = hit
  let end = hit

  while (start > 0 && !isSpace(cells[start - 1]?.char ?? '')) {
    start -= 1
  }

  while (end + 1 < cells.length && !isSpace(cells[end + 1]?.char ?? '')) {
    end += 1
  }

  const first = cells[start]
  const last = cells[end]

  if (!first || !last) {
    return null
  }

  return markBetween(cell.row, first, last)
}

export function lineMark(
  rows: string[],
  cell: Cell,
  omit?: (row: number, column: number) => boolean
): TextMark | null {
  const cells = cellsOn(rows[cell.row - 1] ?? '', cell.row, omit)
  let end = cells.length - 1

  while (end >= 0 && isSpace(cells[end]?.char ?? '')) {
    end -= 1
  }

  const first = cells[0]
  const last = cells[end]

  if (!first || !last) {
    return null
  }

  return markBetween(cell.row, first, last)
}

export function press(
  gesture: Gesture,
  cell: Cell,
  now: number,
  rows: string[],
  omit?: (row: number, column: number) => boolean
): Gesture {
  const again =
    gesture.pressed !== null &&
    sameCell(gesture.pressed, cell) &&
    now - gesture.pressedAt <= CLICK_MS
  const presses = again ? gesture.presses + 1 : 1
  const mark =
    presses >= 3 ? lineMark(rows, cell, omit) :
    presses === 2 ? wordMark(rows, cell, omit) :
    null

  return {
    anchor: cell,
    mark,
    presses,
    pressedAt: now,
    pressed: cell,
    dragging: false
  }
}

export function drag(gesture: Gesture, cell: Cell): Gesture {
  if (!gesture.anchor || gesture.presses > 1) {
    return gesture
  }

  if (!gesture.dragging && sameCell(gesture.anchor, cell)) {
    return gesture
  }

  return {
    ...gesture,
    dragging: true,
    mark: { anchor: gesture.anchor, head: cell }
  }
}

export function release(gesture: Gesture): { gesture: Gesture; copy: boolean; cell: Cell | null } {
  if (!gesture.anchor) {
    return { gesture, copy: false, cell: null }
  }

  const copy = gesture.mark !== null && (gesture.dragging || gesture.presses > 1)

  return {
    gesture: { ...gesture, anchor: null, dragging: false },
    copy,
    cell: gesture.anchor
  }
}
