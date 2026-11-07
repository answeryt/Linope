/** A resource handed to a client: a few facts plus any number of links. */

import { Link } from './link.ts'

class PyTypeError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'TypeError'
  }
}

export class Representation {
  readonly facts: Record<string, unknown>
  readonly links: Link[]

  constructor(facts: Record<string, unknown>, links: Link[] = []) {
    this.links = [...links]
    for (const link of this.links) {
      if (!(link instanceof Link)) throw new PyTypeError('representation links must be Link values')
    }
    this.facts = { ...facts }
  }
}
