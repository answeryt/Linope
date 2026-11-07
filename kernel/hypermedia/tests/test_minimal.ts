import assert from 'node:assert/strict'
import { test } from 'node:test'

import { Link } from '../link.ts'
import { links_for_state } from '../representation_json.ts'
import { parse_action_uri, parse_resource_uri } from '../uri.ts'
import { ResourceKind } from '../../resource/definition.ts'

test('resource kinds are only the process resources', () => {
  assert.deepEqual(
    ResourceKind.members.map(kind => kind.value),
    ['memory', 'tool', 'sandbox', 'network']
  )
})

test('page menu has only state actions', () => {
  const resident = new Set(links_for_state('notes.txt', 'a'.repeat(32), 'resident').map(link => link.relation))
  const swapped = new Set(links_for_state('notes.txt', 'a'.repeat(32), 'swapped').map(link => link.relation))
  assert.deepEqual(resident, new Set(['self', 'content', 'pin', 'swap']))
  assert.deepEqual(swapped, new Set(['self', 'admit']))
})

test('resource uris keep the handle opaque', () => {
  const link = new Link('self', 'C:/private/notes.txt', 'a'.repeat(32))
  const href = `http://127.0.0.1:49152/resources/${link.handle}`
  assert.equal(parse_resource_uri(href), link.handle)
  assert.deepEqual(parse_action_uri(`${href}/pin`), [link.handle, 'pin'])
})
