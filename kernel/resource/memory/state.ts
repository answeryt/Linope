/** Open a memory resource. The body lives in a MemoryStore, not in this dict. */

export function open_state(identity: Record<string, unknown>): Record<string, string> {
  return {
    scope: String(identity.scope || ''),
    backend: String(identity.backend || '')
  }
}
