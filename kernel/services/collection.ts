/** A service is a saved list of process ids. It is not a process. */

import { dumps, isRecord, loads, Path, replaceFile, ValueError } from '../trace/journal.ts'

export class ServiceGroup {
  constructor(
    readonly service_id: number,
    readonly pids: number[]
  ) {}
}

export class ServiceBook {
  readonly path: Path

  constructor(file: string | Path) {
    this.path = new Path(file)
  }

  groups(): ServiceGroup[] {
    if (!this.path.is_file()) return []
    const body = loads(this.path.read_text())
    if (!isRecord(body)) throw new ValueError('The service list has a record that cannot be read')
    const found: ServiceGroup[] = []
    const services = Array.isArray(body.services) ? body.services : []
    for (const item of services) {
      if (!isRecord(item)) throw new ValueError('The service list has a record that cannot be read')
      const extra = Object.keys(item).filter(key => key !== 'id' && key !== 'pids')
      if (extra.length) {
        throw new ValueError(`The service list has fields that must not be saved: ${extra.sort().join(', ')}`)
      }
      if (!('id' in item) || !('pids' in item)) throw new ValueError('The service list is missing fields')
      const serviceId = Number(item.id)
      const pids = Array.isArray(item.pids) ? item.pids.map(pid => Number(pid)) : []
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
    this.path.parent.mkdir({ parents: true, exist_ok: true })
    const temporary = this.path.with_suffix(`${this.path.suffix}.tmp`)
    temporary.write_text(dumps(body, { sortKeys: true }))
    replaceFile(temporary, this.path)
  }
}
