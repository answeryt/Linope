export const PLACEHOLDERS = [
  'Ask me anything…',
  'Try "explain this codebase"',
  'Try "write a test for…"',
  'Try "refactor the auth module"',
  'Try "/help" for commands',
  'Try "fix the lint errors"',
  'Try "how does the config loader work?"',
]

export const FACES = [
  '(｡•́︿•̀｡)',
  '(◔_◔)',
  '(¬‿¬)',
  '( •_•)>⌐■-■',
  '(⌐■_■)',
  '(´･_･`)',
  '◉_◉',
  '(°ロ°)',
  '( ˘⌣˘)♡',
  'ヽ(>∀<☆)☆',
  '٩(๑❛ᴗ❛๑)۶',
  '(⊙_⊙)',
  '(¬_¬)',
  '( ͡° ͜ʖ ͡°)',
  'ಠ_ಠ',
]

export const EMOJI_FRAMES = ['⚕ ', '🌀', '🤔', '✨', '🍵', '🔮']
export const ASCII_FRAMES = ['|', '/', '-', '\\']
export const UNICODE_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

export const VERBS = [
  'pondering',
  'contemplating',
  'musing',
  'cogitating',
  'ruminating',
  'deliberating',
  'mulling',
  'reflecting',
  'processing',
  'reasoning',
  'analyzing',
  'computing',
  'synthesizing',
  'formulating',
  'brainstorming',
]

export const VERB_PAD_LEN = VERBS.reduce((max, v) => Math.max(max, v.length), 0) + 1

export const padVerb = (verb: string) => `${verb}…`.padEnd(VERB_PAD_LEN, ' ')

const FORTUNES = [
  'you are one clean refactor away from clarity',
  'a tiny rename today prevents a huge bug tomorrow',
  'your next commit message will be immaculate',
  'the edge case you are ignoring is already solved in your head',
  'minimal diff, maximal calm',
  'today favors bold deletions over new abstractions',
  'the right helper is already in your codebase',
  'you will ship before overthinking catches up',
  'tests are about to save your future self',
  'your instincts are correctly suspicious of that one branch',
]

const LEGENDARY = [
  'legendary drop: one-line fix, first try',
  'legendary drop: every flaky test passes cleanly',
  'legendary drop: your diff teaches by itself',
]

const hash = (s: string) => [...s].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 16777619), 2166136261) >>> 0

const fromScore = (n: number) => {
  const rare = n % 20 === 0
  const bag = rare ? LEGENDARY : FORTUNES
  return `${rare ? '🌟' : '🔮'} ${bag[n % bag.length]}`
}

export const randomFortune = () => fromScore(Math.floor(Math.random() * 0x7fffffff))
export const dailyFortune = (seed: string) => fromScore(hash(`${seed}|${new Date().toDateString()}`))

export const HOTKEYS: [string, string][] = [
  ['Enter', 'submit the current draft'],
  ['Shift+Enter', 'insert a newline'],
  ['Tab', 'apply completion'],
  ['↑/↓', 'completions / queue edit / history'],
  ['Ctrl+C', 'interrupt / clear draft'],
  ['Ctrl+L', 'new session'],
  ['Ctrl+A / Ctrl+E', 'start / end of line'],
  ['Esc', 'close overlay'],
  ['/<cmd>', 'slash commands — type /help'],
  ['!<cmd>', 'run a shell command (needs a backend)'],
]

export function pickPlaceholder(index = Date.now()): string {
  return PLACEHOLDERS[index % PLACEHOLDERS.length] ?? PLACEHOLDERS[0]!
}
