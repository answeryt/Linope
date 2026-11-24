import { LoopWindow } from "@/desktop/apps/LoopWindow";

export const appId = "loop:linope";

type LinopeDesktopProps = {
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

export default function LinopeDesktop(props: LinopeDesktopProps) {
  return (
    <LoopWindow
      {...props}
      empty="点 + 开一个对话。下面发出的话会交给选中的对话。"
      title="linope"
    />
  );
}
