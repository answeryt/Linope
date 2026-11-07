/** Select links on a page. This module does not run a model turn.

The name remains so older imports keep working. New code should call
kernel.hypermedia.link_selector. Model turns are scheduled by kernel.scheduler.
 */

export { FollowResult, link_named, select_links } from './link_selector.ts'
import { select_links } from './link_selector.ts'

export const follow_selected = select_links
