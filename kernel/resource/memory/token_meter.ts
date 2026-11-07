/** Estimate tokens for text that is about to be sent. Stored rows are not scanned. */

export function estimate_tokens(text: unknown): number {
  const body = typeof text === 'string' ? text : ''
  if (!body) return 0
  return Math.max(1, Math.floor((body.length + 3) / 4))
}

export function count_texts(texts: unknown[]): number {
  return texts.reduce<number>((sum, text) => sum + estimate_tokens(text), 0)
}
