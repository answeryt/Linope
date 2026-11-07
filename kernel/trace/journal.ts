/**
 * An append-only journal of turns. Scheduling does not read it.
 *
 * This module also holds the Python-compatible values the rest of the kernel
 * shares: paths, exceptions, JSON, and context variables. They live here so
 * the migration does not add a new kernel file.
 */

import { AsyncLocalStorage } from 'node:async_hooks'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

export class PyError extends Error {
  constructor(name: string, message = '') {
    super(message)
    this.name = name
  }
}

export class ValueError extends PyError {
  constructor(message = '') {
    super('ValueError', message)
  }
}

export class RuntimeError extends PyError {
  constructor(message = '') {
    super('RuntimeError', message)
  }
}

export class TypeError extends PyError {
  constructor(message = '') {
    super('TypeError', message)
  }
}

export class KeyError extends PyError {
  constructor(message = '') {
    super('KeyError', message)
  }
}

export class PermissionError extends PyError {
  constructor(message = '') {
    super('PermissionError', message)
  }
}

export class OSError extends PyError {
  constructor(message = '') {
    super('OSError', message)
  }
}

export class FileNotFoundError extends PyError {
  constructor(message = '') {
    super('FileNotFoundError', message)
  }
}

export class LookupError extends PyError {
  constructor(message = '') {
    super('LookupError', message)
  }
}

export class NotImplementedError extends PyError {
  constructor(message = '') {
    super('NotImplementedError', message)
  }
}

export class JSONDecodeError extends PyError {
  constructor(message = '') {
    super('JSONDecodeError', message)
  }
}

export class TimeoutExpired extends PyError {
  constructor(message = '') {
    super('TimeoutExpired', message)
  }
}

export function isPy(error: unknown, ...names: string[]): error is PyError {
  return error instanceof Error && names.includes(error.name)
}

export function pyRepr(value: unknown): string {
  if (typeof value === 'string') {
    if (!value.includes("'") && !value.includes('\\')) return `'${value}'`
    return `"${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`
  }
  if (typeof value === 'boolean') return value ? 'True' : 'False'
  if (value === null || value === undefined) return 'None'
  if (typeof value === 'number') {
    if (Number.isNaN(value)) return 'nan'
    if (!Number.isFinite(value)) return value > 0 ? 'inf' : '-inf'
    return String(value)
  }
  return String(value)
}

export function asInt(value: unknown, label = 'int()'): number {
  if (typeof value === 'boolean' || value === null || value === undefined) {
    const shown = value === null || value === undefined ? 'NoneType' : 'bool'
    throw new TypeError(`${label} argument must be a string, a bytes-like object or a real number, not '${shown}'`)
  }
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new ValueError('cannot convert float NaN/inf to integer')
    return Math.trunc(value)
  }
  if (typeof value === 'string') {
    const text = value.trim()
    if (!/^[-+]?\d+$/.test(text)) {
      throw new ValueError(`invalid literal for int() with base 10: ${pyRepr(value)}`)
    }
    return Number(text)
  }
  if (typeof value === 'bigint') return Number(value)
  throw new TypeError(`${label} argument must be a string, a bytes-like object or a real number, not '${typeof value}'`)
}

export function asFloat(value: unknown): number {
  if (typeof value === 'number') return value
  if (typeof value === 'boolean' || value === null || value === undefined) {
    throw new TypeError(`float() argument must be a string or a real number, not '${value === null || value === undefined ? 'NoneType' : 'bool'}'`)
  }
  if (typeof value === 'string') {
    const text = value.trim().toLowerCase()
    if (text === 'nan') return Number.NaN
    if (text === 'inf' || text === 'infinity' || text === '+inf' || text === '+infinity') return Number.POSITIVE_INFINITY
    if (text === '-inf' || text === '-infinity') return Number.NEGATIVE_INFINITY
    if (!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?$/.test(text)) {
      throw new ValueError(`could not convert string to float: ${pyRepr(value.trim())}`)
    }
    return Number(text)
  }
  throw new TypeError(`float() argument must be a string or a real number, not '${typeof value}'`)
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return isPlainObject(value)
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const proto = Object.getPrototypeOf(value)
  return proto === Object.prototype || proto === null
}

export function enumValue(value: unknown): string {
  if (typeof value === 'object' && value !== null && 'value' in value) {
    const inner = (value as { value: unknown }).value
    if (typeof inner === 'string' || typeof inner === 'number') return String(inner)
  }
  return String(value ?? '')
}

export function splitLines(text: string): string[] {
  if (!text) return []
  const parts = text.split(/\r\n|\r|\n|\u2028|\u2029|\v|\f/)
  if (parts.length > 0 && parts[parts.length - 1] === '' && /(?:\r\n|\r|\n|\u2028|\u2029|\v|\f)$/.test(text)) {
    parts.pop()
  }
  return parts
}

type DumpOptions = {
  ensureAscii?: boolean
  sortKeys?: boolean
  indent?: number | null
  defaultFn?: (value: unknown) => unknown
}

export function dumps(value: unknown, options: DumpOptions = {}): string {
  const ensureAscii = options.ensureAscii ?? false
  const sortKeys = options.sortKeys ?? false
  const indent = options.indent ?? null
  return encodeValue(value, options, ensureAscii, sortKeys, indent, 0)
}

export function loads(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    throw new JSONDecodeError(message)
  }
}

function encodeValue(
  value: unknown,
  options: DumpOptions,
  ensureAscii: boolean,
  sortKeys: boolean,
  indent: number | null,
  level: number
): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return encodeNumber(value)
  if (typeof value === 'string') return encodeString(value, ensureAscii)
  if (typeof value === 'bigint') return String(value)
  if (Array.isArray(value)) return encodeArray(value, options, ensureAscii, sortKeys, indent, level)
  if (isPlainObject(value)) return encodeObject(value as Record<string, unknown>, options, ensureAscii, sortKeys, indent, level)
  if (options.defaultFn) return encodeValue(options.defaultFn(value), options, ensureAscii, sortKeys, indent, level)
  throw new TypeError(`Object of type ${typeof value} is not JSON serializable`)
}

function encodeNumber(value: number): string {
  if (Number.isNaN(value)) return 'NaN'
  if (value === Number.POSITIVE_INFINITY) return 'Infinity'
  if (value === Number.NEGATIVE_INFINITY) return '-Infinity'
  if (Object.is(value, -0)) return '0'
  if (Number.isInteger(value)) return String(value)
  const text = JSON.stringify(value)
  return text.includes('.') || text.includes('e') || text.includes('E') ? text : `${text}.0`
}

function encodeString(text: string, ensureAscii: boolean): string {
  let out = '"'
  for (const ch of text) {
    const code = ch.codePointAt(0) ?? 0
    if (ch === '"') out += '\\"'
    else if (ch === '\\') out += '\\\\'
    else if (ch === '\b') out += '\\b'
    else if (ch === '\f') out += '\\f'
    else if (ch === '\n') out += '\\n'
    else if (ch === '\r') out += '\\r'
    else if (ch === '\t') out += '\\t'
    else if (code < 0x20 || code === 0x7f || (ensureAscii && code > 0x7f)) {
      if (code > 0xffff) {
        const hi = Math.floor((code - 0x10000) / 0x400) + 0xd800
        const lo = ((code - 0x10000) % 0x400) + 0xdc00
        out += `\\u${hi.toString(16).padStart(4, '0')}\\u${lo.toString(16).padStart(4, '0')}`
      } else {
        out += `\\u${code.toString(16).padStart(4, '0')}`
      }
    } else out += ch
  }
  return `${out}"`
}

function encodeArray(
  value: unknown[],
  options: DumpOptions,
  ensureAscii: boolean,
  sortKeys: boolean,
  indent: number | null,
  level: number
): string {
  if (value.length === 0) return '[]'
  const gap = indent === null ? '' : '\n' + ' '.repeat(indent * (level + 1))
  const end = indent === null ? '' : '\n' + ' '.repeat(indent * level)
  const sep = indent === null ? ', ' : `,\n${' '.repeat(indent * (level + 1))}`
  const body = value
    .map(item => encodeValue(item, options, ensureAscii, sortKeys, indent, level + 1))
    .join(sep)
  return `[${gap}${body}${end}]`
}

function encodeObject(
  value: Record<string, unknown>,
  options: DumpOptions,
  ensureAscii: boolean,
  sortKeys: boolean,
  indent: number | null,
  level: number
): string {
  const keys = Object.keys(value).filter(key => value[key] !== undefined)
  if (sortKeys) keys.sort()
  if (keys.length === 0) return '{}'
  const colon = ': '
  const sep = indent === null ? ', ' : `,\n${' '.repeat(indent * (level + 1))}`
  const gap = indent === null ? '' : '\n' + ' '.repeat(indent * (level + 1))
  const end = indent === null ? '' : '\n' + ' '.repeat(indent * level)
  const body = keys
    .map(key => `${encodeString(key, ensureAscii)}${colon}${encodeValue(value[key], options, ensureAscii, sortKeys, indent, level + 1)}`)
    .join(sep)
  return `{${gap}${body}${end}}`
}

export function stdout(text: unknown = ''): void {
  fs.writeSync(1, `${String(text)}\n`)
}

export function stderr(text: unknown = ''): void {
  fs.writeSync(2, `${String(text)}\n`)
}

export function utcNowIso(): string {
  const iso = new Date().toISOString()
  const [head, rest] = iso.split('.')
  const millis = (rest || '000Z').slice(0, 3)
  return `${head}.${millis}000+00:00`
}

let pythonPath: string | undefined

export function pythonExecutable(): string {
  const hinted = process.env.LINOPE_PYTHON?.trim() || process.env.PYTHON?.trim()
  if (hinted) return hinted
  if (!pythonPath) {
    pythonPath = execFileSync('python3', ['-c', 'import sys; print(sys.executable)'], {
      encoding: 'utf8'
    }).trim()
  }
  return pythonPath
}

export function argvTail(): string[] {
  return process.argv.slice(2)
}

export function replaceFile(source: Path | string, destination: Path | string): void {
  fs.renameSync(String(source), String(destination))
}

type Frame<T> = { value: T; parent?: Frame<T>; empty?: boolean }

export class ContextVar<T> {
  private readonly als = new AsyncLocalStorage<Frame<T>>()

  constructor(
    readonly name: string,
    private readonly fallback: T
  ) {}

  get(): T {
    const frame = this.als.getStore()
    if (!frame || frame.empty) return this.fallback
    return frame.value
  }

  set(value: T): Frame<T> {
    const frame: Frame<T> = { value, parent: this.als.getStore() }
    this.als.enterWith(frame)
    return frame
  }

  reset(token: Frame<T>): void {
    if (this.als.getStore() !== token) {
      throw new ValueError(`<Token var=${this.name} was created in a different Context>`)
    }
    if (token.parent) this.als.enterWith(token.parent)
    else this.als.enterWith({ value: this.fallback, empty: true })
  }
}

export class Path {
  readonly raw: string

  constructor(value: string | Path = '') {
    this.raw = value instanceof Path ? value.raw : String(value)
  }

  toString(): string {
    return this.raw
  }

  static cwd(): Path {
    return new Path(process.cwd())
  }

  static home(): Path {
    return new Path(os.homedir())
  }

  join(...parts: Array<string | Path>): Path {
    let text = this.raw
    for (const part of parts) {
      const bit = String(part)
      if (!bit) continue
      if (path.isAbsolute(bit)) {
        text = bit
        continue
      }
      if (!text) text = bit
      else if (text.endsWith('/') || text.endsWith('\\')) text += bit
      else text += `${path.sep}${bit}`
    }
    return new Path(text)
  }

  get parent(): Path {
    if (this.raw === '' || this.raw === '.') return new Path('.')
    return new Path(path.dirname(this.raw))
  }

  get name(): string {
    return path.basename(this.raw)
  }

  get stem(): string {
    return path.parse(this.raw).name
  }

  get suffix(): string {
    return path.parse(this.raw).ext
  }

  get parents(): Path[] {
    const found: Path[] = []
    let current = this as Path
    for (;;) {
      const next = current.parent
      if (next.raw === current.raw) break
      found.push(next)
      current = next
    }
    return found
  }

  expanduser(): Path {
    if (this.raw === '~') return Path.home()
    if (this.raw.startsWith('~/') || this.raw.startsWith('~\\')) {
      return new Path(path.join(os.homedir(), this.raw.slice(2)))
    }
    return this
  }

  resolve(): Path {
    const absolute = path.resolve(this.expanduser().raw)
    const missing: string[] = []
    let current = absolute
    while (true) {
      try {
        const real = fs.realpathSync(current)
        return new Path(missing.length === 0 ? real : path.join(real, ...missing.reverse()))
      } catch (error) {
        const code = (error as NodeJS.ErrnoException).code
        if (code !== 'ENOENT') return new Path(path.normalize(absolute))
        const next = path.dirname(current)
        if (next === current) return new Path(path.normalize(absolute))
        missing.push(path.basename(current))
        current = next
      }
    }
  }

  is_absolute(): boolean {
    return path.isAbsolute(this.raw)
  }

  is_file(): boolean {
    try {
      return fs.statSync(this.raw).isFile()
    } catch {
      return false
    }
  }

  is_dir(): boolean {
    try {
      return fs.statSync(this.raw).isDirectory()
    } catch {
      return false
    }
  }

  is_symlink(): boolean {
    try {
      return fs.lstatSync(this.raw).isSymbolicLink()
    } catch {
      return false
    }
  }

  exists(): boolean {
    try {
      fs.lstatSync(this.raw)
      return true
    } catch {
      return false
    }
  }

  read_text(): string {
    return fs.readFileSync(this.raw, 'utf8')
  }

  write_text(data: string): void {
    fs.writeFileSync(this.raw, data, 'utf8')
  }

  read_bytes(): Buffer {
    return fs.readFileSync(this.raw)
  }

  write_bytes(data: Buffer | Uint8Array): void {
    fs.writeFileSync(this.raw, data)
  }

  append_text(data: string): void {
    fs.appendFileSync(this.raw, data, 'utf8')
  }

  mkdir(options?: { parents?: boolean; exist_ok?: boolean }): void {
    fs.mkdirSync(this.raw, { recursive: Boolean(options?.parents || options?.exist_ok) })
  }

  unlink(options?: { missing_ok?: boolean }): void {
    try {
      fs.unlinkSync(this.raw)
    } catch (error) {
      if (options?.missing_ok && (error as NodeJS.ErrnoException).code === 'ENOENT') return
      throw error
    }
  }

  with_name(name: string): Path {
    return this.parent.join(name)
  }

  with_suffix(suffix: string): Path {
    if (suffix && !suffix.startsWith('.')) throw new ValueError(`Invalid suffix ${pyRepr(suffix)}`)
    if (!this.name || this.name === '.' || this.name === '..') {
      throw new ValueError(`${this.raw} has an empty name`)
    }
    return this.parent.join(`${this.stem}${suffix}`)
  }

  relative_to(other: string | Path): Path {
    const base = new Path(other).raw
    const rel = path.relative(base, this.raw)
    if (rel.startsWith('..') || path.isAbsolute(rel)) {
      throw new ValueError(`${pyRepr(this.raw)} is not in the subpath of ${pyRepr(base)}`)
    }
    return new Path(rel || '.')
  }

  as_posix(): string {
    return this.raw.replaceAll('\\', '/')
  }

  stat(): { st_size: number; st_mtime: number } {
    const info = fs.statSync(this.raw)
    return { st_size: info.size, st_mtime: info.mtimeMs / 1000 }
  }

  samefile(other: string | Path): boolean {
    const left = fs.statSync(this.raw)
    const right = fs.statSync(String(other))
    return left.dev === right.dev && left.ino === right.ino
  }

  iterdir(): Path[] {
    return fs.readdirSync(this.raw).map(name => this.join(name))
  }

  touch(): void {
    const handle = fs.openSync(this.raw, 'a')
    fs.closeSync(handle)
    const now = new Date()
    fs.utimesSync(this.raw, now, now)
  }
}

export function journal_path(folder?: string | Path | null): Path {
  const root = folder == null ? Path.cwd() : new Path(folder)
  return root.join('.linope', 'log', 'session.jsonl')
}

export function journal_beside(ledgerPath: string | Path): Path {
  return new Path(ledgerPath).resolve().parent.join('log', 'session.jsonl')
}

export class Journal {
  readonly path: Path

  constructor(file: string | Path) {
    this.path = new Path(file)
  }

  append(event: Record<string, unknown>): void {
    this.path.parent.mkdir({ parents: true, exist_ok: true })
    const line = { time: utcNowIso(), ...event }
    this.path.append_text(`${dumps(line)}${'\n'}`)
  }

  rows(): Array<Record<string, unknown>> {
    if (!this.path.is_file()) return []
    const found: Array<Record<string, unknown>> = []
    for (const raw of splitLines(this.path.read_text())) {
      if (!raw.trim()) continue
      const item = loads(raw)
      if (isRecord(item)) found.push(item)
    }
    return found
  }
}
