import { useLayoutEffect, useRef, useState } from "react";
import { motion, type MotionStyle } from "motion/react";
import { DotIndicator } from "flickering-dots/react";
import type { UiTurn } from "@/desktop/link/state";
import { MessageMarkdown } from "@/desktop/dialog/MessageMarkdown";

const BUBBLE_SPRING = { type: "spring" as const, visualDuration: 0.35, bounce: 0.15 };

const bubbleColumn =
  "flex min-h-full flex-col items-end justify-end gap-2.5 px-5 pb-[22px] pt-11";

function ThinkingIndicator({ reduced }: { reduced: boolean }) {
  return (
    <div
      aria-label="AI 正在思考"
      role="status"
      style={{
        display: "flex",
        flexShrink: 0,
        height: 28,
        width: 28,
      }}
    >
      <DotIndicator
        label="AI 正在思考"
        off="rgba(28,28,30,0.16)"
        on="rgba(28,28,30,0.68)"
        reduced={reduced}
        set="pulse"
        size={28}
        state="thinking"
      />
    </div>
  );
}

function ChatBubbles({
  className = "h-full w-full overflow-x-hidden overflow-y-auto",
  contentClassName = bubbleColumn,
  messages,
  reduced,
  running,
  style,
}: {
  className?: string;
  contentClassName?: string;
  messages: UiTurn[];
  reduced: boolean;
  running: boolean;
  style?: MotionStyle;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const [expandedReasoning, setExpandedReasoning] = useState<Set<string>>(new Set());

  useLayoutEffect(() => {
    const node = listRef.current;
    if (!node) {
      return;
    }
    node.scrollTop = node.scrollHeight;
  }, [messages]);

  const toggleReasoning = (id: string) => {
    setExpandedReasoning((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const streamingAssistant = messages.some(
    (message) => message.role === "assistant" && message.stream,
  );
  const waitingForAssistant = running && !streamingAssistant;

  return (
    <motion.div
      aria-label="对话"
      className={className}
      onWheel={(event) => event.stopPropagation()}
      ref={listRef}
      role="log"
      style={{
        scrollbarWidth: "thin",
        overscrollBehavior: "contain",
        ...style,
      }}
    >
      <div className={contentClassName}>
        {messages.map((message) => {
          const outgoing = message.role === "user";
          const error = message.role === "error";
          const reasoningOpen = expandedReasoning.has(message.id);
          const streaming = message.role === "assistant" && message.stream;
          const messageBody = (
            <>
              {message.role === "assistant" && message.reasoning ? (
                <>
                  <button
                    aria-expanded={reasoningOpen}
                    aria-label={reasoningOpen ? "收起思考过程" : "展开思考过程"}
                    className="cursor-pointer border-0 bg-transparent p-0 text-left"
                    onClick={() => toggleReasoning(message.id)}
                    style={{
                      color: "rgba(28,28,30,0.62)",
                      fontSize: 13,
                      lineHeight: "18px",
                    }}
                    type="button"
                  >
                    {reasoningOpen ? "收起思考过程" : message.stream ? "思考中" : "思考过程"}
                  </button>
                  {reasoningOpen ? (
                    <div
                      style={{
                        color: "rgba(28,28,30,0.68)",
                        fontSize: 13,
                        whiteSpace: "pre-wrap",
                      }}
                    >
                      {message.reasoning}
                    </div>
                  ) : null}
                </>
              ) : null}
              {message.role === "assistant" ? (
                <MessageMarkdown source={message.text} />
              ) : (
                message.text
              )}
            </>
          );
          return (
            <motion.div
              animate={{ opacity: 1, x: 0, scale: 1 }}
              className={`max-w-[78%] ${outgoing ? "self-end" : "self-start"}`}
              initial={reduced ? false : { opacity: 0, x: outgoing ? 28 : -28, scale: 0.96 }}
              key={message.id}
              style={{
                originX: outgoing ? 1 : 0,
                borderRadius: 18,
                padding: "8px 12px",
                background: outgoing
                  ? "rgba(255,255,255,0.55)"
                  : error
                    ? "rgba(255, 225, 225, 0.7)"
                    : "rgba(255,255,255,0.35)",
                color: error ? "#8b1e2d" : "#1c1c1e",
                fontSize: 15,
                lineHeight: "20px",
                display: "flex",
                flexDirection: streaming ? "row" : "column",
                gap: 8,
                alignItems: streaming ? "flex-start" : undefined,
                whiteSpace: message.role === "assistant" ? undefined : "pre-wrap",
                overflowWrap: "anywhere",
              }}
              transition={reduced ? { duration: 0 } : BUBBLE_SPRING}
            >
              {streaming ? (
                <>
                  <div
                    style={{
                      display: "flex",
                      flex: 1,
                      flexDirection: "column",
                      gap: 8,
                      minWidth: 0,
                    }}
                  >
                    {messageBody}
                  </div>
                  <ThinkingIndicator reduced={reduced} />
                </>
              ) : (
                messageBody
              )}
            </motion.div>
          );
        })}
        {waitingForAssistant ? (
          <div
            aria-label="等待 AI 回复"
            className="self-start"
            role="status"
            style={{ padding: "4px 0" }}
          >
            <ThinkingIndicator reduced={reduced} />
          </div>
        ) : null}
      </div>
    </motion.div>
  );
}

export { ChatBubbles };
