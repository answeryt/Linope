export const theme = {
  logo: ['#7EC8FF', '#4DABF7', '#228BE6', '#1C7ED6'] as const,
  border: '#4DABF7',
  surface: '#0E2A43',
  text: '#E7F5FF',
  muted: '#8ECAFF',
  accent: '#7EC8FF',
  error: '#FF8787'
}

export const reset = '\x1b[0m'

export function rgb(hex: string): [number, number, number] {
  const h = hex.slice(1)

  return [Number.parseInt(h.slice(0, 2), 16), Number.parseInt(h.slice(2, 4), 16), Number.parseInt(h.slice(4, 6), 16)]
}

export function paint(hex: string, text = ''): string {
  const [r, g, b] = rgb(hex)

  return `\x1b[38;2;${r};${g};${b}m${text}`
}

export function fill(hex: string): string {
  const [r, g, b] = rgb(hex)

  return `\x1b[48;2;${r};${g};${b}m`
}

export function fg(hex: string, text: string): string {
  return paint(hex, text) + reset
}
