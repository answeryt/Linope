import { fg, theme } from './theme.js'

const LOGO_ART = [
  '██╗     ██╗███╗   ██╗ ██████╗ ██████╗ ███████╗    ██╗  ██╗███████╗██████╗ ███╗   ██╗███████╗██╗     ',
  '██║     ██║████╗  ██║██╔═══██╗██╔══██╗██╔════╝    ██║ ██╔╝██╔════╝██╔══██╗████╗  ██║██╔════╝██║     ',
  '██║     ██║██╔██╗ ██║██║   ██║██████╔╝█████╗█████╗█████╔╝ █████╗  ██████╔╝██╔██╗ ██║█████╗  ██║     ',
  '██║     ██║██║╚██╗██║██║   ██║██╔═══╝ ██╔══╝╚════╝██╔═██╗ ██╔══╝  ██╔══██╗██║╚██╗██║██╔══╝  ██║     ',
  '███████╗██║██║ ╚████║╚██████╔╝██║     ███████╗    ██║  ██╗███████╗██║  ██║██║ ╚████║███████╗███████╗',
  '╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝     ╚══════╝    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝'
]

export const LOGO_WIDTH = Math.max(...LOGO_ART.map(line => line.length))

const logoColor = (index: number) => {
  const last = theme.logo.length - 1
  const slot = Math.round((index / Math.max(1, LOGO_ART.length - 1)) * last)

  return theme.logo[slot] ?? theme.accent
}

export function logoLines(columns: number, rows = 24): string[] {
  const width = Math.max(20, columns - 2)

  // A 6-row block logo plus 8 rows of chrome needs at least 15 terminal rows
  // to stay visible above the prompt without scrolling off the top.
  if (width >= LOGO_WIDTH && rows >= 16) {
    return LOGO_ART.map((line, index) => fg(logoColor(index), line))
  }

  const label = ' LINOPE-KERNEL '
  const rule = Math.max(2, width - label.length)
  const left = Math.floor(rule / 2)

  return [
    fg(theme.logo[0], '═'.repeat(left)) +
      fg(theme.accent, label) +
      fg(theme.logo[0], '═'.repeat(rule - left))
  ]
}
