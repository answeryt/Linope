export const MAX_HISTORY = 100

export type EditorState = {
  input: string
  cursor: number
  history: string[]
  historyIndex: number
  draft: string
}

const charsOf = (text: string) => Array.from(text)

const withInput = (state: EditorState, input: string, cursor = charsOf(input).length): EditorState => ({
  ...state,
  input,
  cursor: Math.max(0, Math.min(cursor, charsOf(input).length))
})

const leaveHistory = (state: EditorState): EditorState => (
  state.historyIndex === -1
    ? state
    : { ...state, historyIndex: -1, draft: '' }
)

export const createEditor = (): EditorState => ({
  input: '',
  cursor: 0,
  history: [],
  historyIndex: -1,
  draft: ''
})

export const recordSubmission = (state: EditorState, text: string): EditorState => {
  const history = state.history.at(-1) === text
    ? state.history
    : [...state.history, text].slice(-MAX_HISTORY)

  return {
    ...state,
    input: '',
    cursor: 0,
    history,
    historyIndex: -1,
    draft: ''
  }
}

export const historyUp = (state: EditorState): EditorState => {
  if (!state.history.length) {
    return state
  }

  const draft = state.historyIndex === -1 ? state.input : state.draft
  const index = state.historyIndex === -1
    ? state.history.length - 1
    : Math.max(0, state.historyIndex - 1)

  return {
    ...state,
    input: state.history[index] ?? '',
    cursor: charsOf(state.history[index] ?? '').length,
    historyIndex: index,
    draft
  }
}

export const historyDown = (state: EditorState): EditorState => {
  if (state.historyIndex === -1) {
    return state
  }

  if (state.historyIndex >= state.history.length - 1) {
    return withInput({ ...state, historyIndex: -1, draft: '' }, state.draft)
  }

  const index = state.historyIndex + 1
  return {
    ...state,
    input: state.history[index] ?? '',
    cursor: charsOf(state.history[index] ?? '').length,
    historyIndex: index
  }
}

export const moveCursor = (state: EditorState, delta: number): EditorState => {
  const next = leaveHistory(state)
  return withInput(next, next.input, next.cursor + delta)
}

export const moveCursorHome = (state: EditorState): EditorState => {
  const next = leaveHistory(state)
  return withInput(next, next.input, 0)
}

export const moveCursorEnd = (state: EditorState): EditorState => {
  const next = leaveHistory(state)
  return withInput(next, next.input)
}

export const insertText = (state: EditorState, text: string): EditorState => {
  const next = leaveHistory(state)
  const chars = charsOf(next.input)
  chars.splice(next.cursor, 0, ...charsOf(text))
  return withInput(next, chars.join(''), next.cursor + charsOf(text).length)
}

export const backspace = (state: EditorState): EditorState => {
  const next = leaveHistory(state)
  if (next.cursor === 0) {
    return next
  }

  const chars = charsOf(next.input)
  chars.splice(next.cursor - 1, 1)
  return withInput(next, chars.join(''), next.cursor - 1)
}

export const deleteForward = (state: EditorState): EditorState => {
  const next = leaveHistory(state)
  const chars = charsOf(next.input)
  if (next.cursor >= chars.length) {
    return next
  }

  chars.splice(next.cursor, 1)
  return withInput(next, chars.join(''), next.cursor)
}
