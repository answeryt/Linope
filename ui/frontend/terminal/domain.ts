import type { Theme } from './theme'
import type { Completion, Role } from './types'

export const ROLE: Record<Role, (t: Theme) => { body: string; glyph: string; prefix: string }> = {
  assistant: (t) => ({ body: t.color.text, glyph: t.brand.tool, prefix: t.color.border }),
  system: (t) => ({ body: t.color.muted, glyph: '·', prefix: t.color.muted }),
  tool: (t) => ({ body: t.color.muted, glyph: '⚡', prefix: t.color.muted }),
  user: (t) => ({ body: t.color.text, glyph: '>', prefix: t.color.text }),
}

export const looksLikeSlashCommand = (text: string) => /^\/[^\s/]*(?:\s|$)/.test(text)

export function parseSlashCommand(cmd: string): { arg: string; cmd: string; name: string } {
  const [name = '', ...rest] = cmd.slice(1).split(/\s+/)
  return { arg: rest.join(' '), cmd, name: name.toLowerCase() }
}

export const applyCompletion = (value: string, rowText: string, replaceAt: number): string => {
  const text = value.startsWith('/') && rowText.startsWith('/') ? rowText.slice(1) : rowText
  return value.slice(0, replaceAt) + text
}

export function completionToApplyOnSubmit(
  value: string,
  rowText: string | undefined,
  replaceAt: number,
): string | null {
  if (!rowText) return null
  const next = applyCompletion(value, rowText, replaceAt)
  return next !== value && next.trimEnd() !== value.trimEnd() ? next : null
}

export function composerPromptText(cwd: string): string {
  return `LE ${cwd.trim() || '~'}>`
}

export function fmtDuration(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  if (total < 60) return `${total}s`
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  if (minutes < 60) return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const remain = minutes % 60
  return remain ? `${hours}h ${remain}m` : `${hours}h`
}

export function fmtK(n: number): string {
  if (n < 1000) return String(Math.round(n))
  const k = n / 1000
  return k < 10 ? `${k.toFixed(1)}k` : `${Math.round(k)}k`
}

export function ctxBar(pct: number, width = 10): string {
  const p = Math.max(0, Math.min(100, pct))
  const filled = Math.round((p / 100) * width)
  return '█'.repeat(filled) + '░'.repeat(width - filled)
}

export function ctxBarColor(pct: number, t: Theme): string {
  if (pct >= 95) return t.color.statusCritical
  if (pct > 80) return t.color.statusBad
  if (pct >= 50) return t.color.statusWarn
  return t.color.statusGood
}

export function shortModelLabel(model: string): string {
  const last = model.split('/').pop() ?? model
  return last
    .replace(/^claude[-_]/, '')
    .replace(/^anthropic[-_]/, '')
    .replace(/[-_]/g, ' ')
    .replace(/\b(\d+)\s+(\d+)\b/g, '$1.$2')
    .trim()
}

export function filterCompletions(input: string, catalog: readonly Completion[]): Completion[] {
  if (!input.startsWith('/')) return []
  const token = input.slice(1).split(/\s/)[0] ?? ''
  const needle = token.toLowerCase()
  return catalog.filter((row) => row.text.slice(1).toLowerCase().startsWith(needle)).slice(0, 12)
}

export function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

export function newId(): string {
  return crypto.randomUUID()
}
