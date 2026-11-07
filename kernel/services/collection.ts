/** A service is a saved list of process ids. It is not a process. */

import fs from 'node:fs'
import path from 'node:path'

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

function pyJson(value: unknown, sortKeys = false): string {
  if (value === null) return 'null'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : JSON.stringify(value)
  if (typeof value === 'string') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(item => pyJson(item, sortKeys)).join(', ')}]`
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (sortKeys) entries.sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0))
    return `{${entries.map(([key, item]) => `${JSON.stringify(key)}: ${pyJson(item, sortKeys)}`).join(', ')}}`
  }
  throw new TypeError(`Object of type ${typeof value} is not JSON serializable`)
}

export class ServiceGroup {
  constructor(
    readonly service_id: number,
    readonly pids: number[]
  ) {}
}

export class ServiceBook {
  readonly path: string

  constructor(file: string) {
    this.path = file
  }

  groups(): ServiceGroup[] {
    if (!fs.existsSync(this.path) || !fs.statSync(this.path).isFile()) return []
    const body = JSON.parse(fs.readFileSync(this.path, 'utf8')) as { services?: unknown }
    if (typeof body !== 'object' || body === null || Array.isArray(body)) {
      throw new ValueError('The service list has a record that cannot be read')
    }
    const found: ServiceGroup[] = []
    const services = Array.isArray(body.services) ? body.services : []
    for (const item of services) {
      if (typeof item !== 'object' || item === null || Array.isArray(item)) {
        throw new ValueError('The service list has a record that cannot be read')
      }
      const record = item as Record<string, unknown>
      const extra = Object.keys(record).filter(key => key !== 'id' && key !== 'pids')
      if (extra.length) {
        throw new ValueError(`The service list has fields that must not be saved: ${extra.sort().join(', ')}`)
      }
      if (!('id' in record) || !('pids' in record)) throw new ValueError('The service list is missing fields')
      const serviceId = Number(record.id)
      const pids = Array.isArray(record.pids) ? record.pids.map(pid => Number(pid)) : []
      if (serviceId <= 0 || !pids.length || pids.some(pid => pid <= 0)) {
        throw new ValueError('A pid in the service list is invalid')
      }
      if (new Set(pids).size !== pids.length) throw new ValueError('The same pid was given twice')
      found.push(new ServiceGroup(serviceId, pids))
    }
    return found
  }

  get(serviceId: number): ServiceGroup | null {
    for (const group of this.groups()) {
      if (group.service_id === Number(serviceId)) return group
    }
    return null
  }

  add(pids: Array<number | string>): ServiceGroup {
    const chosen = pids.map(pid => Number(pid))
    if (!chosen.length || chosen.some(pid => pid <= 0)) {
      throw new ValueError('A service must have at least one process')
    }
    if (new Set(chosen).size !== chosen.length) throw new ValueError('The same pid was given twice')
    const current = this.groups()
    const serviceId = 1 + current.reduce((max, item) => Math.max(max, item.service_id), 0)
    const created = new ServiceGroup(serviceId, chosen)
    this.write([...current, created])
    return created
  }

  private write(groups: ServiceGroup[]): void {
    const body = {
      services: groups.map(item => ({ id: item.service_id, pids: [...item.pids] }))
    }
    fs.mkdirSync(path.dirname(this.path), { recursive: true })
    const temporary = `${this.path}.tmp`
    fs.writeFileSync(temporary, pyJson(body, true), 'utf8')
    fs.renameSync(temporary, this.path)
  }
}
