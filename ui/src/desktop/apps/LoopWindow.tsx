import { prefersReducedMotion } from "@/components/ui/glass-motion";
import { ChatBubbles } from "@/desktop/dialog/ChatBubbles";
import { cardStyle, ink, quiet } from "@/desktop/apps/shell";

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

type LoopProcess = {
  activity: "away" | "busy" | "waiting";
  capability: string;
  id: string;
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
  process?: LoopProcess | null;
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

function cornerStatus(tasks: LoopTask[], process: LoopProcess | null | undefined, title: string) {
  const shown = tasks.find((task) => task.leader) ?? tasks[0];
  const parts: string[] = [];
  if (shown) {
    const step = steps[shown.pc] ?? shown.pc;
    const tool = note(shown.registers.tool);
    parts.push(tool ? `${step} · ${tool}` : step);
  }
  if (process) {
    parts.push(process.capability || title);
    parts.push(activities[process.activity]);
  }
  if (tasks.length > 1) parts.push(`还有 ${tasks.length - 1} 步`);
  return parts.join(" · ");
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
  const status = cornerStatus(tasks, process, title);

  return (
    <div style={{ color: ink, display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ alignItems: "flex-end", display: "flex", height: 44, maxWidth: "46%", minWidth: 0, padding: "0 16px 6px" }}>
        {status ? (
          <p
            style={{
              color: quiet,
              fontSize: 13,
              lineHeight: "18px",
              margin: 0,
              minWidth: 0,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              width: "100%",
            }}
            title={status}
          >
            {status}
          </p>
        ) : null}
      </div>
      <div style={{ display: "flex", flex: 1, gap: 10, minHeight: 0, padding: "0 16px 16px" }}>
        <aside
          style={{
            ...cardStyle,
            display: "flex",
            flex: "0 0 220px",
            flexDirection: "column",
            gap: 8,
            minHeight: 0,
            overflow: "auto",
            padding: 10,
          }}
        >
          <button
            aria-label="新建对话"
            onClick={() => onCreateConversation?.()}
            style={{
              alignSelf: "flex-start",
              background: "rgba(255,255,255,0.38)",
              border: 0,
              borderRadius: 999,
              color: ink,
              cursor: "pointer",
              fontSize: 13,
              lineHeight: "18px",
              padding: "6px 12px",
            }}
            type="button"
          >
            +
          </button>
          {conversations.length === 0 ? (
            <p style={{ color: quiet, fontSize: 13, lineHeight: "18px", margin: 0 }}>{empty}</p>
          ) : null}
          {conversations.map((tab) => {
            const chosen = tab.id === (selected?.id ?? "");
            const label = tabText(tab);
            return (
              <button
                key={tab.id}
                onClick={() => onSelectConversation?.(tab.id)}
                style={{
                  background: chosen ? "rgba(255,255,255,0.82)" : "rgba(255,255,255,0.38)",
                  border: 0,
                  borderRadius: 12,
                  boxSizing: "border-box",
                  color: ink,
                  cursor: "pointer",
                  fontSize: 13,
                  lineHeight: "18px",
                  minWidth: 0,
                  overflow: "hidden",
                  padding: "8px 10px",
                  textAlign: "left",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  width: "100%",
                }}
                title={label}
                type="button"
              >
                {label}
              </button>
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
