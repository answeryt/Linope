import { LoopWindow } from "@/desktop/apps/LoopWindow";

export const appId = "loop:pi";

type PiDesktopProps = {
  conversations?: Array<{
    id: string;
    pid: string;
    queued: number;
    running: boolean;
  }>;
  messages?: Array<{
    id: string;
    reasoning?: string;
    role: "assistant" | "error" | "system" | "user";
    stream?: boolean;
    text: string;
  }>;
  onCreateConversation?: () => void;
  onSelectConversation?: (id: string) => void;
  process?: {
    activity: "away" | "busy" | "waiting";
    capability: string;
    id: string;
  } | null;
  selectedId?: string;
  tasks?: Array<{
    id: string;
    leader: boolean;
    pc: string;
    pid: string;
    registers: Record<string, unknown>;
  }>;
};

export default function PiDesktop(props: PiDesktopProps) {
  return (
    <LoopWindow
      {...props}
      empty="点 + 开一个对话。任务怎么推进由这里安排，文件和搜索仍用已经安装的应用。"
      title="pi"
    />
  );
}
