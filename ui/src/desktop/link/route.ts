export type SendRoute =
  | { kind: "loop"; appId: string; capability: string }
  | { kind: "choose" };

export function routeDraft(toolAppId: string | null, loops: Record<string, string>): SendRoute {
  if (toolAppId) {
    const capability = loops[toolAppId];
    if (capability) return { kind: "loop", appId: toolAppId, capability };
  }
  return { kind: "choose" };
}

export function loopAppId(loops: Record<string, string>, capability = "agent_loop"): string {
  return Object.entries(loops).find(([, name]) => name === capability)?.[0] ?? "";
}
