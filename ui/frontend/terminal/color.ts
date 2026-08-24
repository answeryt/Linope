export type Rgb = readonly [number, number, number]

const HEX6 = /^#?([0-9a-f]{6})$/i
const HEX3 = /^#?([0-9a-f]{3})$/i
const RGB_FN = /^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})/i

const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)))

export function parseColor(input: string): Rgb | null {
  const value = input.trim()
  let match = HEX6.exec(value)
  if (match) {
    const n = parseInt(match[1]!, 16)
    return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff]
  }
  match = HEX3.exec(value)
  if (match) {
    const [r, g, b] = match[1]!
    return [parseInt(r! + r!, 16), parseInt(g! + g!, 16), parseInt(b! + b!, 16)]
  }
  match = RGB_FN.exec(value)
  if (match) {
    return [clamp(Number(match[1])), clamp(Number(match[2])), clamp(Number(match[3]))]
  }
  return null
}

export const toHex = (rgb: Rgb): string =>
  '#' + rgb.map((c) => clamp(c).toString(16).padStart(2, '0')).join('')

export function mix(a: string, b: string, t: number): string {
  const pa = parseColor(a)
  const pb = parseColor(b)
  if (!pa || !pb) return a
  return toHex([
    pa[0] + (pb[0] - pa[0]) * t,
    pa[1] + (pb[1] - pa[1]) * t,
    pa[2] + (pb[2] - pa[2]) * t,
  ])
}

function channelLuminance(value: number): number {
  const n = value / 255
  return n <= 0.03928 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4
}

export function relativeLuminance(color: string): number | null {
  const rgb = parseColor(color)
  return rgb
    ? 0.2126 * channelLuminance(rgb[0]) + 0.7152 * channelLuminance(rgb[1]) + 0.0722 * channelLuminance(rgb[2])
    : null
}

export function grayOf(color: string): string {
  const rgb = parseColor(color)
  if (!rgb) return color
  const gray = clamp(0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2])
  return toHex([gray, gray, gray])
}

export const desaturate = (color: string, s: number) => mix(color, grayOf(color), s)
