import { prefersReducedMotion } from "@/components/ui/glass-motion";
import { ChatBubbles } from "@/desktop/dialog/ChatBubbles";

export const appId = "loop:linope";

type ConversationTab = {
  id: string;
  pid: string;
  queued: number;
  running: boolean;
};

type LinopeDesktopProps = {
  capability?: string;
  conversations?: ConversationTab[];
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

const quiet = "rgba(60, 60, 67, 0.72)";

const activities = {
  waiting: "等待",
  busy: "进行中",
  away: "离开",
} as const;

const bubbleColumn =
  "flex min-h-full flex-col items-end justify-end gap-2.5 px-5 pb-[22px] pt-2";

function tabText(tab: ConversationTab) {
  const name = tab.pid || "新对话";
  if (tab.queued > 0) return `${name} · 排队 ${tab.queued}`;
  if (tab.running) return `${name} · 进行中`;
  return `${name} · 等待`;
}

export default function LinopeDesktop({
  capability,
  conversations = [],
  messages = [],
  onCreateConversation,
  onSelectConversation,
  process,
  selectedId,
}: LinopeDesktopProps) {
  const reduced = prefersReducedMotion();
  const selected = conversations.find((item) => item.id === selectedId) ?? conversations[0];
  const status = process
    ? `${process.id} · ${process.capability || capability || "agent_loop"} · ${activities[process.activity]}`
    : "点 + 开一个对话。下面发出的话会交给选中的对话。";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        style={{
          display: "flex",
          gap: 8,
          overflowX: "auto",
          padding: "44px 20px 0",
          scrollbarWidth: "none",
        }}
      >
        {conversations.map((tab) => {
          const chosen = tab.id === (selected?.id ?? "");
          return (
            <button
              className="cursor-pointer border-0"
              key={tab.id}
              onClick={() => onSelectConversation?.(tab.id)}
              style={{
                flex: "0 0 auto",
                borderRadius: 999,
                padding: "6px 12px",
                background: chosen ? "rgba(255,255,255,0.82)" : "rgba(255,255,255,0.38)",
                color: "#1c1c1e",
                fontSize: 13,
                lineHeight: "18px",
              }}
              type="button"
            >
              {tabText(tab)}
            </button>
          );
        })}
        <button
          aria-label="新建对话"
          className="cursor-pointer border-0"
          onClick={() => onCreateConversation?.()}
          style={{
            flex: "0 0 auto",
            borderRadius: 999,
            padding: "6px 12px",
            background: "rgba(255,255,255,0.38)",
            color: "#1c1c1e",
            fontSize: 13,
            lineHeight: "18px",
          }}
          type="button"
        >
          +
        </button>
      </div>
      <p
        style={{
          margin: 0,
          padding: "8px 20px 0",
          fontSize: 15,
          lineHeight: "22px",
          color: quiet,
        }}
      >
        {status}
      </p>
      <ChatBubbles
        className="min-h-0 w-full flex-1 overflow-x-hidden overflow-y-auto"
        contentClassName={bubbleColumn}
        messages={messages}
        reduced={reduced}
        running={Boolean(selected?.running)}
      />
    </div>
  );
}
