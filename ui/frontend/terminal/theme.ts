import { desaturate, grayOf, mix, relativeLuminance } from './color'

export interface ThemeColors {
  accent: string
  bg: string
  border: string
  completionBg: string
  completionCurrentBg: string
  error: string
  label: string
  muted: string
  ok: string
  primary: string
  prompt: string
  selectionBg: string
  sessionBorder: string
  sessionLabel: string
  shellDollar: string
  statusBad: string
  statusBg: string
  statusCritical: string
  statusFg: string
  statusGood: string
  statusWarn: string
  text: string
  thinking: string
  tool: string
  warn: string
}

export interface ThemeBrand {
  goodbye: string
  helpHeader: string
  icon: string
  name: string
  prompt: string
  tool: string
  welcome: string
}

export interface Theme {
  brand: ThemeBrand
  color: ThemeColors
}

export interface ThemeSeeds {
  accent: string
  activeRow?: string
  bg: string
  border?: string
  error: string
  muted?: string
  ok: string
  primary: string
  prompt?: string
  selection?: string
  shellDollar: string
  statusBad: string
  statusCritical: string
  statusGood: string
  statusWarn: string
  surface?: string
  text: string
  warn: string
}

const BRAND: ThemeBrand = {
  goodbye: 'Goodbye! ⚕',
  helpHeader: '(^_^)? Commands',
  icon: '',
  name: 'Hermes Agent',
  prompt: '>',
  tool: '┊',
  welcome: 'Type your commands',
}

export const DARK_SEEDS: ThemeSeeds = {
  accent: '#FFBF00',
  activeRow: '#333355',
  bg: '#101014',
  border: '#CD7F32',
  error: '#ef5350',
  ok: '#4caf50',
  primary: '#FFD700',
  prompt: '#CCCCCC',
  selection: '#3a3a55',
  shellDollar: '#4dabf7',
  statusBad: '#FF8C00',
  statusCritical: '#FF6B6B',
  statusGood: '#8FBC8F',
  statusWarn: '#FFD700',
  surface: '#1a1a2e',
  text: '#FFF8DC',
  warn: '#ffa726',
}

export const LIGHT_SEEDS: ThemeSeeds = {
  accent: '#956E00',
  bg: '#ffffff',
  border: '#A56628',
  error: '#C14240',
  ok: '#367E39',
  primary: '#867000',
  prompt: '#2B2014',
  shellDollar: '#377BB3',
  statusBad: '#A65A00',
  statusCritical: '#B94D4D',
  statusGood: '#5C7A5C',
  statusWarn: '#867000',
  text: '#3D2F13',
  warn: '#956115',
}

function deriveTones(seeds: ThemeSeeds) {
  const { accent, bg, text } = seeds
  const isLight = (relativeLuminance(bg) ?? 0) > 0.5
  const surface = mix(bg, desaturate(accent, 0.15), isLight ? 0.045 : 0.09)
  return {
    activeRow: mix(surface, accent, 0.25),
    border: mix(accent, bg, 0.25),
    label: isLight ? desaturate(mix(accent, text, 0.03), 0.15) : desaturate(mix(accent, bg, 0.13), 0.16),
    muted: isLight ? desaturate(accent, 0.05) : desaturate(mix(accent, bg, 0.19), 0.16),
    selection: isLight && seeds.shellDollar ? mix(bg, seeds.shellDollar, 0.2) : mix(surface, accent, 0.28),
    statusFg: grayOf(mix(text, bg, isLight ? 0.3 : 0.24)),
    surface,
  }
}

export function buildPalette(seeds: ThemeSeeds): ThemeColors {
  const tones = deriveTones(seeds)
  const surface = seeds.surface ?? tones.surface
  const activeRow = seeds.activeRow ?? (seeds.surface ? mix(surface, seeds.accent, 0.22) : tones.activeRow)
  const muted = seeds.muted ?? tones.muted
  return {
    accent: seeds.accent,
    bg: seeds.bg,
    border: seeds.border ?? tones.border,
    completionBg: surface,
    completionCurrentBg: activeRow,
    error: seeds.error,
    label: tones.label,
    muted,
    ok: seeds.ok,
    primary: seeds.primary,
    prompt: seeds.prompt ?? seeds.text,
    selectionBg: seeds.selection ?? tones.selection,
    sessionBorder: muted,
    sessionLabel: muted,
    shellDollar: seeds.shellDollar,
    statusBad: seeds.statusBad,
    statusBg: surface,
    statusCritical: seeds.statusCritical,
    statusFg: tones.statusFg,
    statusGood: seeds.statusGood,
    statusWarn: seeds.statusWarn,
    text: seeds.text,
    thinking: muted,
    tool: seeds.accent,
    warn: seeds.warn,
  }
}

export const DARK_THEME: Theme = { brand: BRAND, color: buildPalette(DARK_SEEDS) }
export const LIGHT_THEME: Theme = { brand: BRAND, color: buildPalette(LIGHT_SEEDS) }

export function themeForProduct(name: string, dark = true): Theme {
  const base = dark ? DARK_THEME : LIGHT_THEME
  return {
    ...base,
    brand: { ...base.brand, name },
  }
}

export function applyTheme(root: HTMLElement, theme: Theme): void {
  const { color } = theme
  const vars: Record<string, string> = {
    '--tui-accent': color.accent,
    '--tui-bg': color.bg,
    '--tui-border': color.border,
    '--tui-chip': color.completionCurrentBg,
    '--tui-error': color.error,
    '--tui-label': color.label,
    '--tui-muted': color.muted,
    '--tui-ok': color.ok,
    '--tui-primary': color.primary,
    '--tui-prompt': color.prompt,
    '--tui-selection': color.selectionBg,
    '--tui-shell': color.shellDollar,
    '--tui-status-bad': color.statusBad,
    '--tui-status-bg': color.statusBg,
    '--tui-status-critical': color.statusCritical,
    '--tui-status-fg': color.statusFg,
    '--tui-status-good': color.statusGood,
    '--tui-status-warn': color.statusWarn,
    '--tui-surface': color.completionBg,
    '--tui-text': color.text,
    '--tui-thinking': color.thinking,
    '--tui-tool': color.tool,
    '--tui-warn': color.warn,
  }
  for (const el of [root, document.documentElement]) {
    for (const [key, value] of Object.entries(vars)) {
      el.style.setProperty(key, value)
    }
  }
}
