import '../terminal/style.css'
import { mountTerminal } from '../terminal/mount'

const root = document.getElementById('root')
if (root === null) throw new Error('ui frontend: missing #root')
const mount: HTMLElement = root

const product = document.title.trim() || 'Linope'
mount.innerHTML =
  '<div class="boot" role="status" aria-busy="true"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>'

boot().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : 'ui: terminal failed'
  mount.innerHTML = `<div class="boot error" role="alert">${escapeText(message)}</div>`
})

async function boot(): Promise<void> {
  await mountTerminal(mount, product)
}

function escapeText(value: string): string {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
}
