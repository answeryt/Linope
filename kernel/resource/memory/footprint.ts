/** Budget for one model request. History is not included unless this read names it. */

import { resolve_default_context_length } from '../../calculate/measure.ts'
import { PromptFootprint } from './records.ts'
import { estimate_tokens } from './token_meter.ts'

export function reserves(limit: number): [number, number] {
  if (limit <= 0) return [0, 0]
  return [Math.max(1, Math.floor(limit / 8)), Math.max(1, Math.floor(limit / 50))]
}

export function footprint(options: {
  context_limit: number
  system?: string
  message?: string
  action?: string
  read?: string
}): PromptFootprint {
  const [output, safety] = reserves(options.context_limit)
  return new PromptFootprint(
    options.context_limit,
    estimate_tokens(options.system || ''),
    estimate_tokens(options.message || ''),
    estimate_tokens(options.action || ''),
    estimate_tokens(options.read || ''),
    output,
    safety
  )
}

export function context_limit_for(model: string): number {
  return Number(resolve_default_context_length(model || 'unknown/model'))
}
