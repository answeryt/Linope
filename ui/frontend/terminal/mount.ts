import { paint, paintStatus, shellMarkup } from './render'
import { createStore, type TerminalStore } from './state'
import { applyTheme } from './theme'

function autosize(area: HTMLTextAreaElement): void {
  area.style.height = 'auto'
  area.style.height = `${Math.min(area.scrollHeight, 128)}px`
}

function bind(root: HTMLElement, store: TerminalStore): void {
  const form = root.querySelector('.tui-composer')
  const area = root.querySelector('#tui-input')
  if (!(form instanceof HTMLFormElement) || !(area instanceof HTMLTextAreaElement)) return

  let tick = Math.floor(Math.random() * 1000)
  let redrawQueued = false

  const redraw = () => {
    if (redrawQueued) return
    redrawQueued = true
    requestAnimationFrame(() => {
      redrawQueued = false
      const state = store.get()
      applyTheme(root, state.theme)
      paint(root, store, tick)
      if (area.value !== state.input) area.value = state.input
      autosize(area)
    })
  }

  store.subscribe(redraw)
  redraw()

  window.setInterval(() => {
    tick += 1
    if (store.get().statusBar !== 'off') paintStatus(root, store, tick)
  }, 900)

  window.addEventListener('resize', redraw)

  area.addEventListener('input', () => {
    store.setInput(area.value)
    autosize(area)
  })

  area.addEventListener('keydown', (event) => {
    const state = store.get()
    if (event.key === 'Escape') {
      store.closeOverlay()
      return
    }
    if (event.key === 'Tab' && state.completions.length) {
      event.preventDefault()
      store.selectCompletion(state.compIdx)
      return
    }
    if (event.key === 'ArrowUp' && !event.shiftKey) {
      event.preventDefault()
      store.walkHistory(-1)
      return
    }
    if (event.key === 'ArrowDown' && !event.shiftKey) {
      event.preventDefault()
      store.walkHistory(1)
      return
    }
    if (event.key === 'l' && event.ctrlKey) {
      event.preventDefault()
      store.newSession('new session started')
      return
    }
    if (event.key === 'c' && event.ctrlKey && area.selectionStart === area.selectionEnd) {
      event.preventDefault()
      if (state.busy) {
        store.patch({ busy: false, status: 'ready', turnStartedAt: null })
        return
      }
      if (state.input) store.setInput('')
      return
    }
    if (event.key !== 'Enter' || event.shiftKey || event.altKey) return
    event.preventDefault()
    if (state.completions.length) {
      const row = state.completions[state.compIdx]
      if (row && row.text.slice(1) !== parseToken(state.input)) {
        store.selectCompletion(state.compIdx)
        return
      }
    }
    store.submit(area.value)
  })

  form.addEventListener('submit', (event) => {
    event.preventDefault()
    store.submit(area.value)
  })

  root.addEventListener('click', (event) => {
    const target = event.target
    if (!(target instanceof Element)) return
    const complete = target.closest('[data-comp]')
    if (complete instanceof HTMLElement && complete.dataset.comp) {
      store.selectCompletion(Number(complete.dataset.comp))
      area.focus()
      return
    }
    const session = target.closest('[data-session]')
    if (session instanceof HTMLElement && session.dataset.session) {
      store.resume(session.dataset.session)
      area.focus()
      return
    }
    const model = target.closest('[data-model]')
    if (model instanceof HTMLElement && model.dataset.model) {
      store.patch({ model: model.dataset.model, overlay: 'none' })
      area.focus()
      return
    }
    const action = target.closest('[data-action]')
    if (!(action instanceof HTMLElement)) return
    if (action.dataset.action === 'sessions') store.patch({ overlay: 'sessions' })
    if (action.dataset.action === 'new-session') store.newSession('new session started')
    if (action.dataset.action === 'confirm-yes') store.confirmDestructive()
    if (action.dataset.action === 'confirm-no') store.closeOverlay()
    area.focus()
  })

  root.addEventListener('mousedown', (event) => {
    const target = event.target
    if (!(target instanceof Element)) return
    if (target.closest('textarea, button, a, [data-overlay]')) return
    event.preventDefault()
    area.focus()
  })

  area.focus()
}

function parseToken(input: string): string {
  return input.slice(1).split(/\s/)[0] ?? ''
}

export async function mountTerminal(host: HTMLElement, product: string): Promise<void> {
  const store = createStore(product)
  host.innerHTML = shellMarkup(store.get())
  const root = host.querySelector('[data-tui]')
  if (!(root instanceof HTMLElement)) throw new Error('ui terminal: mount failed')
  applyTheme(root, store.get().theme)
  bind(root, store)
  await store.hydrate()
}
