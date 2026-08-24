import type { ThemeColors } from './theme'

export type ArtLine = [string, string]

const LOGO_ART = [
  '██╗     ██╗███╗   ██╗ ██████╗ ██████╗ ███████╗',
  '██║     ██║████╗  ██║██╔═══██╗██╔══██╗██╔════╝',
  '██║     ██║██╔██╗ ██║██║   ██║██████╔╝█████╗  ',
  '██║     ██║██║╚██╗██║██║   ██║██╔═══╝ ██╔══╝  ',
  '███████╗██║██║ ╚████║╚██████╔╝██║     ███████╗',
  '╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝     ╚══════╝',
]

export const LOGO_BLUE = '#3B78FF'

export const LOGO_WIDTH = Math.max(...LOGO_ART.map((line) => line.length))

export const logoLines = (): string[] => LOGO_ART

const TAG_FULL = 'Nous Research · Messenger of the Digital Gods'
const HIDE_BELOW = 34

const clip = (s: string, w: number) => (w <= 0 ? '' : s.length > w ? `${s.slice(0, Math.max(0, w - 1))}…` : s)

const centerIn = (s: string, w: number) => {
  const f = clip(s, w)
  const slack = Math.max(0, w - f.length)
  const left = slack >> 1
  return `${' '.repeat(left)}${f}${' '.repeat(slack - left)}`
}

const ruleIn = (label: string, w: number) => {
  const f = clip(label, Math.max(1, w - 4))
  const slack = Math.max(0, w - f.length - 2)
  const left = slack >> 1
  return `${'─'.repeat(left)} ${f} ${'─'.repeat(slack - left)}`
}

export type BannerKind = 'hidden' | 'compact' | 'logo'

export function bannerKind(cols: number): BannerKind {
  if (cols < HIDE_BELOW) return 'hidden'
  if (cols >= LOGO_WIDTH + 2) return 'logo'
  return 'compact'
}

export function compactBanner(name: string, cols: number, color: ThemeColors): ArtLine[] {
  const w = Math.max(28, cols - 4)
  return [
    [LOGO_BLUE, ruleIn(name, w)],
    [color.muted, centerIn(TAG_FULL, w)],
    [LOGO_BLUE, '─'.repeat(w)],
  ]
}

export { TAG_FULL }
