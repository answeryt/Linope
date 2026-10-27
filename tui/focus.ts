import type { Key } from './keys.js'

export type Focus = 'input' | 'history'

export type Command =
  | { type: 'quit' }
  | { type: 'ctrl-d' }
  | { type: 'focus'; focus: Focus }
  | { type: 'scroll'; delta: number }
  | { type: 'scroll-page'; direction: -1 | 1 }
  | { type: 'scroll-edge'; edge: 'top' | 'bottom' }
  | { type: 'editor'; key: Key }
  | { type: 'submit' }
  | { type: 'none' }

const other = (focus: Focus): Focus => (focus === 'input' ? 'history' : 'input')

export function bindingFor(focus: Focus, key: Key): Command {
  if (key.name === 'ctrl-c') {
    return { type: 'quit' }
  }

  if (key.name === 'ctrl-d') {
    return { type: 'ctrl-d' }
  }

  if (key.name === 'tab' || key.name === 'shift-tab') {
    return { type: 'focus', focus: other(focus) }
  }

  if (key.name === 'shift-up') {
    return { type: 'scroll', delta: -1 }
  }

  if (focus === 'history') {
    if (key.name === 'up') {
      return { type: 'scroll', delta: -1 }
    }

    if (key.name === 'down') {
      return { type: 'scroll', delta: 1 }
    }

    if (key.name === 'page up') {
      return { type: 'scroll-page', direction: -1 }
    }

    if (key.name === 'page down') {
      return { type: 'scroll-page', direction: 1 }
    }

    if (key.name === 'home') {
      return { type: 'scroll-edge', edge: 'top' }
    }

    if (key.name === 'end') {
      return { type: 'scroll-edge', edge: 'bottom' }
    }

    return { type: 'none' }
  }

  if (key.name === 'return') {
    return { type: 'submit' }
  }

  if (
    key.name === 'up' ||
    key.name === 'down' ||
    key.name === 'left' ||
    key.name === 'right' ||
    key.name === 'home' ||
    key.name === 'end' ||
    key.name === 'backspace' ||
    key.name === 'delete' ||
    key.name === 'char'
  ) {
    return { type: 'editor', key }
  }

  return { type: 'none' }
}
