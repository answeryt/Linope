import { prefersReducedMotion } from "@/components/ui/glass-motion";
import { ChatBubbles } from "@/desktop/dialog/ChatBubbles";
import { EmptyPane, cardStyle, ink, quiet } from "@/desktop/apps/shell";

type ConversationTab = {
  id: string;
  pid: string;
  queued: number;
  running: boolean;
};

type LoopTask = {
  id: string;
  leader: boolean;
  pc: string;
  pid: string;
  registers: Record<string, unknown>;
};

type LoopWindowProps = {
  conversations?: ConversationTab[];
  empty: string;
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
  tasks?: LoopTask[];
  title: string;
};

const activities = {
  waiting: "等待",
  busy: "进行中",
  away: "离开",
} as const;

const steps: Record<string, string> = {
  idle: "空闲",
  ask_model: "问模型",
  using_model: "占用核",
  wait_tool: "等工具",
  wait_helpers: "等帮手",
  answer: "回答",
  done: "结束",
};

function tabText(tab: ConversationTab) {
  const name = tab.pid || "新对话";
  if (tab.queued > 0) return `${name} · 排队 ${tab.queued}`;
  if (tab.running) return `${name} · 进行中`;
  return `${name} · 等待`;
}

function note(value: unknown) {
  return typeof value === "string" ? value : "";
}

function LoopWindow({
  conversations = [],
  empty,
  messages = [],
  onCreateConversation,
  onSelectConversation,
  process,
  selectedId,
  tasks = [],
  title,
}: LoopWindowProps) {
  const reduced = prefersReducedMotion();
  const selected = conversations.find((item) => item.id === selectedId) ?? conversations[0];
  const status = process
    ? `${process.id} · ${process.capability || title} · ${activities[process.activity]}`
    : empty;

  return (
    <div style={{ color: ink, display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ display: "flex", gap: 8, overflowX: "auto", padding: "44px 16px 0" }}>
        {conversations.map((tab) => {
          const chosen = tab.id === (selected?.id ?? "");
          return (
            <button
              key={tab.id}
              onClick={() => onSelectConversation?.(tab.id)}
              style={{
                background: chosen ? "rgba(255,255,255,0.82)" : "rgba(255,255,255,0.38)",
                border: 0,
                borderRadius: 999,
                color: ink,
                cursor: "pointer",
                flex: "0 0 auto",
                fontSize: 13,
                lineHeight: "18px",
                padding: "6px 12px",
              }}
              type="button"
            >
              {tabText(tab)}
            </button>
          );
        })}
        <button
          aria-label="新建对话"
          onClick={() => onCreateConversation?.()}
          style={{
            background: "rgba(255,255,255,0.38)",
            border: 0,
            borderRadius: 999,
            color: ink,
            cursor: "pointer",
            flex: "0 0 auto",
            fontSize: 13,
            lineHeight: "18px",
            padding: "6px 12px",
          }}
          type="button"
        >
          +
        </button>
      </div>
      <p style={{ color: quiet, fontSize: 13, lineHeight: "18px", margin: 0, padding: "8px 16px 0" }}>{status}</p>
      <div style={{ display: "flex", flex: 1, gap: 10, minHeight: 0, padding: "10px 16px 16px" }}>
        <aside
          style={{
            ...cardStyle,
            display: "flex",
            flex: "0 0 196px",
            flexDirection: "column",
            gap: 8,
            minHeight: 0,
            overflow: "auto",
            padding: 10,
          }}
        >
          <span style={{ fontSize: 13, fontWeight: 650, lineHeight: "18px" }}>这一步</span>
          {tasks.length === 0 ? <EmptyPane>还没有任务。</EmptyPane> : null}
          {tasks.map((task) => {
            const tool = note(task.registers.tool);
            return (
              <div key={`${task.pid}:${task.id}`} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontSize: 14, lineHeight: "20px" }}>{task.leader ? "主任务" : task.id}</span>
                <span style={{ color: quiet, fontSize: 12, lineHeight: "16px" }}>
                  {steps[task.pc] ?? task.pc}
                  {tool ? ` · ${tool}` : ""}
                </span>
              </div>
            );
          })}
        </aside>
        <ChatBubbles
          className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto"
          contentClassName="flex min-h-full flex-col items-end justify-end gap-2.5 px-4 pb-4 pt-2"
          messages={messages}
          reduced={reduced}
          running={Boolean(selected?.running)}
          style={cardStyle}
        />
      </div>
    </div>
  );
}

export type { LoopWindowProps };
export { LoopWindow };
