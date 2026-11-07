/** One hypermedia link: a relation and the resource it points at. */

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

export class Link {
  constructor(
    readonly relation: string,
    readonly resource_id: string,
    readonly handle = ''
  ) {
    if (!this.relation) throw new ValueError('link relation is required')
    if (!this.resource_id) throw new ValueError('link resource_id is required')
  }

  can_follow(): boolean {
    return Boolean(this.handle)
  }
}
