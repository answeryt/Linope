import { dailyFortune, HOTKEYS, randomFortune } from './content'
import { looksLikeSlashCommand, parseSlashCommand } from './domain'
import type { Completion, OverlayKind, SlashCommand } from './types'

export const SLASH_COMMANDS: SlashCommand[] = [
  { aliases: ['exit'], help: 'leave a goodbye note', name: 'quit' },
  { help: 'list commands + hotkeys', name: 'help' },
  { aliases: ['new'], help: 'start a new session', name: 'clear' },
  { help: 'force a full UI repaint', name: 'redraw' },
  { help: 'show live session info', name: 'status' },
  { help: 'name the current session', name: 'title', usage: '/title <name>' },
  { help: 'toggle compact transcript', name: 'density' },
  { help: 'agent detail visibility', name: 'details', usage: '/details [hidden|collapsed|expanded|cycle]' },
  { help: 'show a local fortune', name: 'fortune', usage: '/fortune [random|daily]' },
  { help: 'copy the last assistant reply', name: 'copy' },
  { help: 'walk input history', name: 'history' },
  { aliases: ['q'], help: 'show queued drafts', name: 'queue' },
  { help: 'undo the last user turn', name: 'undo' },
  { help: 'retry the last user turn', name: 'retry' },
  { help: 'show or set the model label', name: 'model', usage: '/model [name]' },
  { aliases: ['switch', 'session', 'resume'], help: 'browse sessions', name: 'sessions' },
  { help: 'list currently available tools', name: 'tools' },
  { help: 'list currently available skills', name: 'skills' },
  { help: 'interrupt the current run', name: 'stop' },
  { help: 'show token usage', name: 'usage' },
  { help: 'busy indicator style', name: 'indicator', usage: '/indicator [kaomoji|emoji|ascii|unicode]' },
  { aliases: ['sb'], help: 'status bar placement', name: 'statusbar', usage: '/statusbar [top|bottom|off]' },
  { help: 'show or change the prompt glyph', name: 'prompt', usage: '/prompt [glyph]' },
]

const byName = new Map<string, SlashCommand>(
  SLASH_COMMANDS.flatMap((cmd) => [cmd.name, ...(cmd.aliases ?? [])].map((name) => [name, cmd] as const)),
)

export const findSlashCommand = (name: string) => byName.get(name.toLowerCase())

export function slashCatalog(): Completion[] {
  return SLASH_COMMANDS.map((cmd) => ({
    help: cmd.help,
    text: `/${cmd.name}`,
  }))
}

export function slashHelpSections(): { rows?: [string, string][]; title: string }[] {
  return [
    {
      rows: SLASH_COMMANDS.map((cmd) => [
        `/${cmd.name}${cmd.aliases?.length ? ` (${cmd.aliases.map((a) => `/${a}`).join(', ')})` : ''}`,
        cmd.help,
      ]),
      title: 'Commands',
    },
    { rows: HOTKEYS, title: 'Hotkeys' },
  ]
}

export { dailyFortune, looksLikeSlashCommand, parseSlashCommand, randomFortune }

export type SlashResult =
  | { kind: 'overlay'; overlay: OverlayKind }
  | { kind: 'ok' }
  | { kind: 'unknown'; name: string }
