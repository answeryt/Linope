import { bannerKind, compactBanner, logoLines } from './banner'
import { ASCII_FRAMES, EMOJI_FRAMES, FACES, padVerb, UNICODE_FRAMES, VERBS } from './content'
import { composerPromptText, ctxBar, ctxBarColor, escapeHtml, fmtDuration, fmtK, ROLE, shortModelLabel } from './domain'
import type { TerminalState, TerminalStore } from './state'
import type { IndicatorStyle, Msg, PanelSection } from './types'

function bannerHtml(state: TerminalState, cols: number): string {
  const kind = bannerKind(cols)
  if (kind === 'hidden') return ''
  if (kind === 'logo') {
    return `<pre class="tui-art tui-logo">${escapeHtml(logoLines().join('\n'))}</pre>`
  }
  const compact = compactBanner(state.theme.brand.name, cols, state.theme.color)
    .map(([, text]) => text)
    .join('\n')
  return `<pre class="tui-art tui-logo">${escapeHtml(compact)}</pre>`
}

function sessionPanel(state: TerminalState): string {
  return `
    <div class="tui-session">
      <div class="tui-le-prompt">${escapeHtml(composerPromptText(state.cwd))}</div>
      <div class="tui-welcome">${escapeHtml(state.theme.brand.welcome)}</div>
    </div>
  `
}

function renderPanelSection(section: PanelSection): string {
  const title = section.title ? `<div class="tui-panel-h">${escapeHtml(section.title)}</div>` : ''
  if (section.text) return `${title}<div class="tui-panel-text">${escapeHtml(section.text)}</div>`
  if (section.items) {
    return `${title}<ul class="tui-panel-list">${section.items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
  }
  if (section.rows) {
    return `${title}<table class="tui-panel-table">${section.rows
      .map(
        ([k, v]) =>
          `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(v)}</td></tr>`,
      )
      .join('')}</table>`
  }
  return title
}

function messageHtml(msg: Msg, state: TerminalState, index: number, firstUser: number): string {
  const t = state.theme
  if (msg.kind === 'intro') {
    return `<article class="tui-block tui-intro">${bannerHtml(state, cols())}${msg.info ? sessionPanel(state) : ''}</article>`
  }
  if (msg.kind === 'panel' && msg.panel) {
    return `<article class="tui-block tui-panel">
      <div class="tui-panel-title" style="color:${t.color.primary}">${escapeHtml(msg.panel.title)}</div>
      ${msg.panel.sections.map(renderPanelSection).join('')}
    </article>`
  }
  const role = ROLE[msg.role](t)
  const sep =
    msg.role === 'user' && firstUser >= 0 && index > firstUser
      ? `<div class="tui-turn-rule" style="color:${t.color.border}">───</div>`
      : ''
  const bodyClass = state.compact ? 'tui-msg compact' : 'tui-msg'
  return `${sep}<article class="${bodyClass} role-${msg.role}">
    <span class="tui-glyph" style="color:${role.prefix}">${escapeHtml(role.glyph)}</span>
    <pre class="tui-body" style="color:${role.body}">${escapeHtml(msg.text || ' ')}</pre>
  </article>`
}

function cols(): number {
  const ch = 8.4
  return Math.max(32, Math.floor((window.innerWidth - 48) / ch))
}

function indicatorFrame(style: IndicatorStyle, tick: number): { frame: string; showVerb: boolean } {
  if (style === 'kaomoji') return { frame: FACES[tick % FACES.length] ?? '', showVerb: true }
  if (style === 'emoji') return { frame: EMOJI_FRAMES[tick % EMOJI_FRAMES.length] ?? '⚕ ', showVerb: true }
  if (style === 'ascii') return { frame: ASCII_FRAMES[tick % ASCII_FRAMES.length] ?? '|', showVerb: true }
  return { frame: UNICODE_FRAMES[tick % UNICODE_FRAMES.length] ?? '⠋', showVerb: false }
}

export function statusHtml(state: TerminalState, now: number, tick: number): string {
  if (state.statusBar === 'off') return ''
  const t = state.theme
  const model = shortModelLabel(state.model)
  const pct = state.usage.context_percent
  const ctx = state.usage.context_max
    ? `${fmtK(state.usage.context_used)}/${fmtK(state.usage.context_max)}`
    : state.usage.total
      ? `${fmtK(state.usage.total)} tok`
      : ''
  const bar = state.usage.context_max && cols() >= 72 ? ctxBar(pct) : ''
  const barColor = ctxBarColor(pct, t)
  const session = state.sessions.find((row) => row.id === state.selectedSessionId)
  const duration = session ? fmtDuration(now - session.startedAt) : ''
  const idle = !state.busy && state.lastTurnEndedAt ? `✓ ${fmtDuration(now - state.lastTurnEndedAt)}` : ''
  const { frame, showVerb } = indicatorFrame(state.indicator, tick)
  const verb = VERBS[tick % VERBS.length] ?? ''
  const leftBusy = state.busy
    ? `<span class="tui-status-busy" style="color:${t.color.accent}">${escapeHtml(frame)}${showVerb ? ` ${escapeHtml(padVerb(verb))}` : ''} · ${escapeHtml(fmtDuration(now - (state.turnStartedAt ?? now)))}</span>`
    : `<span style="color:${t.color.statusFg}">${escapeHtml(state.status)}</span>`

  return `<div class="tui-status" role="status">
    <div class="tui-status-left">
      <span style="color:${t.color.border}">─ </span>
      ${leftBusy}
      <span style="color:${t.color.muted}"> │ ${escapeHtml(model)}</span>
      ${ctx ? `<span style="color:${t.color.muted}"> │ ${escapeHtml(ctx)}</span>` : ''}
      ${bar ? `<span style="color:${barColor}"> │ [${escapeHtml(bar)}] ${pct}%</span>` : ''}
      ${duration ? `<span style="color:${t.color.muted}"> │ ${escapeHtml(duration)}</span>` : ''}
      ${idle ? `<span style="color:${t.color.muted}"> │ ${escapeHtml(idle)}</span>` : ''}
      <span class="tui-sessions-chip" data-action="sessions" style="color:${t.color.accent}"> │ ${state.sessions.length} ${state.sessions.length === 1 ? 'session' : 'sessions'}</span>
    </div>
    <div class="tui-status-right" style="color:${t.color.label}">${escapeHtml(state.cwd)}</div>
  </div>`
}

export function transcriptHtml(state: TerminalState): string {
  const session = state.sessions.find((row) => row.id === state.selectedSessionId)
  const messages = session?.messages ?? []
  const firstUser = messages.findIndex((msg) => msg.role === 'user')
  return messages.map((msg, index) => messageHtml(msg, state, index, firstUser)).join('')
}

export function queueHtml(state: TerminalState): string {
  if (!state.queue.length) return ''
  return `<div class="tui-queue">${state.queue
    .map(
      (item, index) =>
        `<div class="tui-queue-row${index === state.queueEditIdx ? ' active' : ''}"><span>queued</span> ${escapeHtml(item.text)}</div>`,
    )
    .join('')}</div>`
}

export function completionsHtml(state: TerminalState): string {
  if (!state.completions.length) return ''
  return `<div class="tui-complete" role="listbox">${state.completions
    .map(
      (row, index) =>
        `<button type="button" class="tui-complete-row${index === state.compIdx ? ' current' : ''}" data-comp="${index}" role="option"><span>${escapeHtml(row.text)}</span><em>${escapeHtml(row.help)}</em></button>`,
    )
    .join('')}</div>`
}

export function overlayHtml(state: TerminalState): string {
  if (state.overlay === 'sessions') {
    return `<div class="tui-overlay" data-overlay="sessions">
      <div class="tui-float">
        <div class="tui-float-title">sessions</div>
        ${state.sessions
          .map(
            (row) =>
              `<button type="button" class="tui-float-row${row.id === state.selectedSessionId ? ' current' : ''}" data-session="${row.id}">${escapeHtml(row.title)} <em>${escapeHtml(row.id.slice(0, 8))}</em></button>`,
          )
          .join('')}
        <button type="button" class="tui-float-row" data-action="new-session">+ new session</button>
      </div>
    </div>`
  }
  if (state.overlay === 'model') {
    const models = ['local', state.model].filter((item, index, all) => all.indexOf(item) === index)
    return `<div class="tui-overlay" data-overlay="model">
      <div class="tui-float">
        <div class="tui-float-title">model</div>
        ${models
          .map(
            (name) =>
              `<button type="button" class="tui-float-row${name === state.model ? ' current' : ''}" data-model="${escapeHtml(name)}">${escapeHtml(name)}</button>`,
          )
          .join('')}
        <p class="tui-float-hint">type /model name to set another label</p>
      </div>
    </div>`
  }
  if (state.overlay === 'confirm' && state.confirm) {
    return `<div class="tui-overlay" data-overlay="confirm">
      <div class="tui-float tui-confirm">
        <div class="tui-float-title">${escapeHtml(state.confirm.title)}</div>
        <p>${escapeHtml(state.confirm.detail)}</p>
        <div class="tui-confirm-actions">
          <button type="button" class="tui-btn danger" data-action="confirm-yes">${escapeHtml(state.confirm.confirmLabel)}</button>
          <button type="button" class="tui-btn" data-action="confirm-no">${escapeHtml(state.confirm.cancelLabel)}</button>
        </div>
      </div>
    </div>`
  }
  return ''
}

export function shellMarkup(state: TerminalState): string {
  const prompt = composerPromptText(state.cwd)
  const status = statusHtml(state, Date.now(), 0)
  return `
    <div class="tui" data-tui>
      ${state.statusBar === 'top' ? `<div class="tui-status-slot top">${status}</div>` : ''}
      <div class="tui-stage">
        <div class="tui-scroll">
          <div class="tui-transcript"></div>
          <div class="tui-dock">
            <div class="tui-queue-slot"></div>
            ${state.statusBar === 'bottom' ? `<div class="tui-status-slot bottom">${status}</div>` : ''}
            <div class="tui-complete-slot"></div>
            <form class="tui-composer">
              <label class="tui-prompt" for="tui-input">${escapeHtml(prompt)}</label>
              <textarea id="tui-input" name="prompt" rows="1" spellcheck="false" autocomplete="off" placeholder=""></textarea>
            </form>
          </div>
        </div>
        <div class="tui-gutter" aria-hidden="true"></div>
      </div>
      <div class="tui-overlay-slot"></div>
    </div>
  `
}

export function paintStatus(root: HTMLElement, store: TerminalStore, tick: number): void {
  const status = statusHtml(store.get(), Date.now(), tick)
  root.querySelectorAll('.tui-status-slot').forEach((slot) => {
    slot.innerHTML = status
  })
}

export function paint(root: HTMLElement, store: TerminalStore, tick: number): void {
  const state = store.get()
  const transcript = root.querySelector('.tui-transcript')
  const queue = root.querySelector('.tui-queue-slot')
  const complete = root.querySelector('.tui-complete-slot')
  const overlay = root.querySelector('.tui-overlay-slot')
  const prompt = root.querySelector('.tui-prompt')
  const input = root.querySelector('#tui-input')
  if (transcript) transcript.innerHTML = transcriptHtml(state)
  if (queue) queue.innerHTML = queueHtml(state)
  if (complete) complete.innerHTML = completionsHtml(state)
  if (overlay) overlay.innerHTML = overlayHtml(state)
  paintStatus(root, store, tick)
  if (prompt instanceof HTMLElement) {
    prompt.textContent = composerPromptText(state.cwd)
    prompt.classList.toggle('shell', state.input.startsWith('!'))
  }
  if (input instanceof HTMLTextAreaElement && input.value !== state.input) {
    input.value = state.input
  }
  const scroll = root.querySelector('.tui-scroll')
  if (scroll instanceof HTMLElement) scroll.scrollTop = scroll.scrollHeight
}

export { cols }
