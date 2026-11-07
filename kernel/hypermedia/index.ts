/** Minimal local HATEOAS resource representations. */

export { representation_for_file } from './file_link.ts'
export { FollowResult, follow_selected, link_named } from './follow.ts'
export { Link } from './link.ts'
export { Representation } from './representation.ts'
export {
  content_payload,
  file_resource_payload,
  link_payload,
  links_for_state,
  representation_payload
} from './representation_json.ts'
export {
  action_uri,
  content_uri,
  parse_action_uri,
  parse_content_uri,
  parse_resource_uri,
  resource_uri
} from './uri.ts'
