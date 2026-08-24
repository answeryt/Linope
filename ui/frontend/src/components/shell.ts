import {
  iconAttach,
  iconFilter,
  iconFolder,
  iconMode,
  iconPanel,
  iconPlus,
  iconSearch,
  iconSend,
  iconSettings,
} from '../icons'
import type { Session, ShellState, Workspace } from '../types'

function selectedWorkspace(state: ShellState) {
  const id = state.selectedWorkspaceId
  if (id === null) return null
  return state.workspaces.find((item) => item.id === id) ?? null
}

export function appMarkup(_state: ShellState, product: string): string {
  return `
    <div class="app">
      <aside class="sidebar" id="sidebar">
        <div class="sidebar-inner">
          <div class="sidebar-top">
            <div class="brand">
              <img src="/favicon.png" alt="" width="28" height="28" />
              <span class="brand-name">${escapeHtml(product)}</span>
            </div>
            <button class="icon-btn sidebar-toggle" type="button" aria-controls="sidebar" aria-expanded="true" aria-label="折叠侧栏">${iconPanel}</button>
          </div>
          <button class="new-session" type="button" disabled aria-disabled="true">${iconPlus}<span>新会话</span></button>
          <section class="workspace-block" aria-labelledby="workspace-heading">
            <div class="workspace-head">
              <h2 id="workspace-heading">工作区</h2>
              <div class="workspace-tools">
                <button class="icon-btn" type="button" disabled aria-disabled="true" aria-label="搜索">${iconSearch}</button>
                <button class="icon-btn" type="button" disabled aria-disabled="true" aria-label="筛选">${iconFilter}</button>
              </div>
            </div>
            <ul class="workspace-list"></ul>
            <ul class="session-list"></ul>
          </section>
          <div class="sidebar-foot">
            <button class="settings" type="button" disabled aria-disabled="true">${iconSettings}<span>设置</span></button>
          </div>
        </div>
      </aside>
      <main class="main">
        <button class="icon-btn sidebar-open" type="button" aria-controls="sidebar" aria-expanded="true" aria-label="打开侧栏">${iconPanel}</button>
        <div class="stage">
          <div class="messages" hidden></div>
          <div class="hero">
            <div class="hero-title">
              <img src="/favicon.png" alt="" width="48" height="48" />
              <h1>${escapeHtml(product)}</h1>
            </div>
            <div class="chips"></div>
          </div>
          <form class="composer">
            <label class="sr-only" for="prompt">消息</label>
            <textarea id="prompt" name="prompt" rows="3" placeholder="描述你想要构建的内容" autocomplete="off"></textarea>
            <div class="composer-bar">
              <div class="composer-left">
                <button class="icon-btn" type="button" disabled aria-disabled="true" aria-label="添加">${iconAttach}</button>
              </div>
              <div class="composer-right">
                <span class="chip model" hidden>${iconMode}<span></span></span>
                <button class="send" type="submit" disabled aria-disabled="true" aria-label="发送">${iconSend}</button>
              </div>
            </div>
          </form>
        </div>
      </main>
    </div>
  `
}

export function renderLists(
  root: HTMLElement,
  state: ShellState,
): void {
  const workspaces = root.querySelector('.workspace-list')
  const sessions = root.querySelector('.session-list')
  if (workspaces === null || sessions === null) return
  workspaces.replaceChildren(
    ...state.workspaces.map((item) => workspaceRow(item, item.id === state.selectedWorkspaceId)),
  )
  sessions.replaceChildren(
    ...state.sessions.map((item) => sessionRow(item, item.id === state.selectedSessionId)),
  )
}

export function renderMessages(root: HTMLElement, state: ShellState): void {
  const host = root.querySelector('.messages')
  const hero = root.querySelector('.hero')
  const stage = root.querySelector('.stage')
  if (host === null || !(host instanceof HTMLElement) || hero === null) return
  const empty = state.messages.length === 0
  host.hidden = empty
  if (hero instanceof HTMLElement) hero.hidden = !empty
  if (stage instanceof HTMLElement) stage.classList.toggle('has-messages', !empty)
  if (empty) {
    host.replaceChildren()
    return
  }
  host.replaceChildren(
    ...state.messages.map((item) => {
      const bubble = document.createElement('div')
      bubble.className = `bubble ${item.role}`
      bubble.textContent = item.text
      return bubble
    }),
  )
}

export function renderChips(root: HTMLElement, state: ShellState): void {
  const chips = root.querySelector('.chips')
  const modelChip = root.querySelector('.chip.model')
  if (chips === null) return
  const workspace = selectedWorkspace(state)
  chips.replaceChildren()
  if (workspace !== null) {
    const chip = document.createElement('span')
    chip.className = 'chip'
    chip.innerHTML = iconFolder
    const label = document.createElement('span')
    label.textContent = workspace.name
    chip.append(label)
    chips.append(chip)
  }
  if (modelChip instanceof HTMLElement) {
    const label = modelChip.querySelector('span')
    if (state.model !== null && label !== null) {
      label.textContent = state.model
      modelChip.hidden = false
    } else {
      modelChip.hidden = true
    }
  }
}

function workspaceRow(item: Workspace, active: boolean): HTMLLIElement {
  const row = document.createElement('li')
  const button = document.createElement('button')
  button.type = 'button'
  button.className = active ? 'workspace-row active' : 'workspace-row'
  button.innerHTML = iconFolder
  const name = document.createElement('span')
  name.textContent = item.name
  button.append(name)
  row.append(button)
  return row
}

function sessionRow(item: Session, active: boolean): HTMLLIElement {
  const row = document.createElement('li')
  const button = document.createElement('button')
  button.type = 'button'
  button.className = active ? 'session-row active' : 'session-row'
  button.textContent = item.title
  row.append(button)
  return row
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}
