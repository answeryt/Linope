/** Turn one file on disk into a representation that can be followed. */

import { Link } from './link.ts'
import { Representation } from './representation.ts'

export function representation_for_file(file: string, handle: string): Representation {
  return new Representation({ path: file }, [new Link('self', file, handle)])
}
