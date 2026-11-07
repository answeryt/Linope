/** Choose links on a representation. Selecting a link does not run it. */

import { Link } from './link.ts'
import { Representation } from './representation.ts'

export class FollowResult {
  constructor(
    readonly followed: Link[],
    readonly left: Link[]
  ) {}
}

export function select_links(representation: Representation, selected: Iterable<string>): FollowResult {
  const chosen = new Set(selected)
  const followed: Link[] = []
  const left: Link[] = []
  for (const link of representation.links) {
    if (chosen.has(link.resource_id) && link.can_follow()) followed.push(link)
    else left.push(link)
  }
  return new FollowResult(followed, left)
}

export function link_named(representation: Representation, relation: string): Link | null {
  for (const link of representation.links) {
    if (link.relation === relation && link.can_follow()) return link
  }
  return null
}
