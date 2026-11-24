import identity from "../../../../capability/prompt/prompt_card/linope/identity.md?raw";
import protocol from "../../../../example/linope.md?raw";
import tools from "../../../../capability/prompt/prompt_card/linope/system_02_tools.md?raw";

const PI_PREAMBLE =
  "我是使用了 Pi 项目的 Linope 工具。关于 Pi 项目，可以查看：https://github.com/earendil-works/pi.git";

type LoadedLoop = {
  id: string;
  name: string;
  capability: string;
  text: string;
  note: string;
};

function joinPrompt(parts: string[]): string {
  return parts.map((part) => part.trim()).filter(Boolean).join("\n\n");
}

const loadedLoops: LoadedLoop[] = [
  {
    id: "loop:linope",
    name: "linope",
    capability: "agent_loop",
    text: joinPrompt([identity, protocol, tools]),
    note: "这段是循环启动时拼好的，每轮问模型时放在最前面。它不写入记忆。",
  },
  {
    id: "loop:pi",
    name: "pi",
    capability: "agent_loop_pi",
    text: PI_PREAMBLE,
    note: "这是追加的开场白。其余提示词在 Pi 进程里生成，桌面拿不到全文。",
  },
];

function installedLoops(ids: readonly string[]): LoadedLoop[] {
  return loadedLoops.filter((loop) => ids.includes(loop.id));
}

function promptText(loop: LoadedLoop, overrides: Readonly<Record<string, string>>): string {
  return loop.id in overrides ? overrides[loop.id] : loop.text;
}

function loadedPromptText(ids: readonly string[], overrides: Readonly<Record<string, string>> = {}): string {
  const chosen = installedLoops(ids);
  const loop =
    chosen.find((item) => item.id === "loop:linope") ?? chosen.find((item) => item.id === "loop:pi");
  return loop ? promptText(loop, overrides) : "";
}

function loopIdForCapability(capability: string): string {
  return loadedLoops.find((loop) => loop.capability === capability)?.id ?? "";
}

function installedLoopLabel(ids: readonly string[]): string {
  const names = installedLoops(ids).map((loop) => loop.name);
  return names.length > 0 ? names.join("、") : "还没有";
}

export type { LoadedLoop };
export { installedLoopLabel, installedLoops, loadedPromptText, loopIdForCapability, promptText };
