import identity from "../../../../capability/prompt/prompt_card/linope/identity.md?raw";
import protocol from "../../../../example/linope.md?raw";
import tools from "../../../../capability/prompt/prompt_card/linope/system_02_tools.md?raw";
import linopeCard from "../../../../capability/agent_loop/linope.json";
import piCard from "../../../../capability/agent_loop/pi/linope.json";

const PI_PREAMBLE =
  "我是使用了 Pi 项目的 Linope 工具。关于 Pi 项目，可以查看：https://github.com/earendil-works/pi.git";

type MemoryCard = {
  resources?: Array<{ kind?: string; identity?: { scope?: string } }>;
};

type LoadedLoop = {
  id: string;
  name: string;
  scope: string;
  text: string;
  note: string;
};

function scopeOf(card: MemoryCard): string {
  for (const resource of card.resources ?? []) {
    if (resource.kind !== "memory") continue;
    const scope = resource.identity?.scope?.trim();
    if (scope) return scope;
  }
  return "chat";
}

function joinPrompt(parts: string[]): string {
  return parts.map((part) => part.trim()).filter(Boolean).join("\n\n");
}

const loadedLoops: LoadedLoop[] = [
  {
    id: "loop:linope",
    name: "linope",
    scope: scopeOf(linopeCard),
    text: joinPrompt([identity, protocol, tools]),
    note: "这段是循环启动时拼好的，每轮问模型时放在最前面。它不写入记忆。",
  },
  {
    id: "loop:pi",
    name: "pi",
    scope: scopeOf(piCard),
    text: PI_PREAMBLE,
    note: "这是追加的开场白。其余提示词在 Pi 进程里生成，桌面拿不到全文。",
  },
];

function installedLoops(ids: readonly string[]): LoadedLoop[] {
  return loadedLoops.filter((loop) => ids.includes(loop.id));
}

function addressScopes(ids: readonly string[]): string[] {
  const chosen = installedLoops(ids);
  const source = chosen.length > 0 ? chosen : loadedLoops;
  return [...new Set(source.map((loop) => loop.scope))];
}

function loadedPromptText(ids: readonly string[]): string {
  const chosen = installedLoops(ids);
  return (
    chosen.find((loop) => loop.id === "loop:linope")?.text ??
    chosen.find((loop) => loop.id === "loop:pi")?.text ??
    ""
  );
}

function installedLoopLabel(ids: readonly string[]): string {
  const names = installedLoops(ids).map((loop) => loop.name);
  return names.length > 0 ? names.join("、") : "还没有";
}

export type { LoadedLoop };
export { addressScopes, installedLoopLabel, installedLoops, loadedPromptText };
