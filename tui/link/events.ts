export type DisplayEvent =
  | { href: string; type: 'image' }
  | { cwd: string; env: string; store: string; text: string; type: 'session' }
  | { text: string; type: 'error' }
  | { text: string; type: 'status' }
  | { text: string; type: 'text' }
  | { text: string; type: 'text-delta' }
  | { type: 'done' }

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null

const textOf = (value: unknown) => (typeof value === 'string' ? value : '')

export function parseEvent(line: string): DisplayEvent | null {
  const raw = line.trim()

  if (!raw.startsWith('{')) {
    return null
  }

  try {
    const payload = asRecord(JSON.parse(raw))

    if (!payload || typeof payload.type !== 'string') {
      return null
    }

    if (payload.type === 'done') {
      return { type: 'done' }
    }

    if (payload.type === 'image') {
      const href = textOf(payload.href)

      return href ? { href, type: 'image' } : null
    }

    if (payload.type === 'session') {
      return {
        cwd: textOf(payload.cwd),
        env: textOf(payload.env) || '未配置',
        store: textOf(payload.store),
        text: textOf(payload.text),
        type: 'session'
      }
    }

    if (payload.type === 'text' || payload.type === 'text-delta' || payload.type === 'status' || payload.type === 'error') {
      return { text: textOf(payload.text), type: payload.type }
    }
  } catch {
    return null
  }

  return null
}
