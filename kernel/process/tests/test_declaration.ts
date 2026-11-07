import assert from 'node:assert/strict'
import { test } from 'node:test'

import { ProcessDeclaration, ResourceClaim, stamp_memory_space } from '../declaration.ts'

test('space is stamped onto the memory claim', () => {
  const declaration = stamp_memory_space(
    new ProcessDeclaration('sample.capability', [new ResourceClaim('memory', { scope: 'chat' })]),
    [['space', 'message,artifact']]
  )
  assert.equal(declaration.resources[0].call_params.space, 'message,artifact')
  assert.throws(() => stamp_memory_space(declaration, [['space', 'page']]), /Unknown memory class/)
})
