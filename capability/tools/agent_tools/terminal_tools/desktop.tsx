import { useEffect, useRef, useState } from "react";
import {
  AppFrame,
  EmptyPane,
  ErrorLine,
  buttonStyle,
  cardStyle,
  fieldStyle,
  ink,
  quiet,
  runCall,
  type CapabilityCaller,
} from "@/desktop/apps/shell";

export const appId = "terminal:终端";

type Session = { cwd: string; id: string; name: string };

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export default function TerminalDesktop({ call, cwd = "" }: { call?: CapabilityCaller; cwd?: string }) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [output, setOutput] = useState("");
  const [line, setLine] = useState("");
  const [error, setError] = useState("");
  const queue = useRef(Promise.resolve());
  const view = useRef<HTMLPreElement>(null);
  const live = useRef(new Set<string>());

  function enqueue<T>(work: () => Promise<T>) {
    const run = queue.current.then(work, work);
    queue.current = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
  }

  function ask(body: Record<string, unknown>) {
    if (!call) return Promise.reject(new Error("当前没有连上内核，不能直接操作。"));
    return enqueue(() =>
      runCall(call, {
        body,
        capability: "tools.terminal_desktop",
        cwd,
        hold: true,
        kind: "tool",
      }),
    );
  }

  async function refresh() {
    const payload = await ask({ action: "list" });
    const rows = Array.isArray(payload.sessions) ? (payload.sessions as Array<Record<string, unknown>>) : [];
    setSessions(
      rows.map((item) => ({
        cwd: String(item.cwd || ""),
        id: String(item.sessionId || ""),
        name: String(item.name || "终端"),
      })),
    );
  }

  async function openSession() {
    const payload = await ask({ action: "open", cwd, name: `终端 ${sessions.length + 1}` });
    const id = String(payload.sessionId || "");
    if (id) live.current.add(id);
    setSessionId(id);
    setOutput("");
    await refresh();
  }

  useEffect(() => {
    if (!call) {
      setError("当前没有连上内核，不能直接操作。");
      return;
    }
    let cancel = false;
    ask({ action: "open", cwd, name: "终端 1" })
      .then(async (payload) => {
        const id = String(payload.sessionId || "");
        if (cancel) {
          if (id) {
            await runCall(call, {
              body: { action: "close", sessionId: id },
              capability: "tools.terminal_desktop",
              cwd,
              hold: true,
              kind: "tool",
            });
          }
          return;
        }
        if (id) live.current.add(id);
        setSessionId(id);
        setOutput("");
        const listed = await ask({ action: "list" });
        if (cancel) return;
        const rows = Array.isArray(listed.sessions) ? (listed.sessions as Array<Record<string, unknown>>) : [];
        setSessions(
          rows.map((item) => ({
            cwd: String(item.cwd || ""),
            id: String(item.sessionId || ""),
            name: String(item.name || "终端"),
          })),
        );
      })
      .catch((caught: unknown) => {
        if (!cancel) setError(caught instanceof Error ? caught.message : String(caught));
      });
    return () => {
      cancel = true;
      const ids = [...live.current];
      live.current.clear();
      for (const id of ids) {
        void runCall(call, {
          body: { action: "close", sessionId: id },
          capability: "tools.terminal_desktop",
          cwd,
          hold: true,
          kind: "tool",
        }).catch(() => undefined);
      }
    };
  }, [call, cwd]);

  useEffect(() => {
    if (!call || !sessionId) return;
    let cancel = false;
    const pump = async () => {
      while (!cancel) {
        try {
          const payload = await ask({ action: "read", sessionId });
          if (!cancel) setOutput(String(payload.text || ""));
        } catch (caught) {
          if (!cancel) setError(caught instanceof Error ? caught.message : String(caught));
        }
        await wait(500);
      }
    };
    void pump();
    return () => {
      cancel = true;
    };
  }, [call, sessionId]);

  useEffect(() => {
    const node = view.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [output]);

  return (
    <AppFrame>
      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={() => openSession().catch((caught: unknown) => setError(caught instanceof Error ? caught.message : String(caught)))} style={buttonStyle} type="button">
          新窗口
        </button>
        <button
          onClick={() => {
            if (!sessionId) return;
            ask({ action: "signal", sessionId }).catch((caught: unknown) =>
              setError(caught instanceof Error ? caught.message : String(caught)),
            );
          }}
          style={buttonStyle}
          type="button"
        >
          中断
        </button>
        <button
          onClick={() => {
            if (!sessionId) return;
            const closing = sessionId;
            ask({ action: "close", sessionId: closing })
              .then(() => {
                live.current.delete(closing);
                setSessions((current) => current.filter((item) => item.id !== closing));
                setSessionId("");
                setOutput("");
              })
              .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : String(caught)));
          }}
          style={buttonStyle}
          type="button"
        >
          关闭
        </button>
      </div>
      <ErrorLine>{error}</ErrorLine>
      <div style={{ display: "flex", flex: 1, gap: 10, minHeight: 0 }}>
        <div style={{ ...cardStyle, flex: "0 0 180px", minHeight: 0, overflow: "auto", padding: 8 }}>
          {sessions.length === 0 ? <EmptyPane>还没有命令窗口。</EmptyPane> : null}
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => setSessionId(session.id)}
              style={{
                background: session.id === sessionId ? "rgba(255,255,255,0.82)" : "transparent",
                border: 0,
                borderRadius: 10,
                color: ink,
                cursor: "pointer",
                display: "block",
                fontSize: 14,
                lineHeight: "20px",
                padding: "6px 8px",
                textAlign: "left",
                width: "100%",
              }}
              type="button"
            >
              {session.name}
              <span style={{ color: quiet, display: "block", fontSize: 12, lineHeight: "16px" }}>{session.cwd || "当前目录"}</span>
            </button>
          ))}
        </div>
        <div style={{ ...cardStyle, display: "flex", flex: 1, flexDirection: "column", minHeight: 0, minWidth: 0, padding: 10 }}>
          <pre
            ref={view}
            style={{
              color: ink,
              flex: 1,
              fontFamily: "ui-monospace, Consolas, monospace",
              fontSize: 13,
              lineHeight: "18px",
              margin: 0,
              overflow: "auto",
              whiteSpace: "pre-wrap",
            }}
          >
            {output || "输入一行命令，结果会留在这个窗口里。"}
          </pre>
          <input
            aria-label="命令"
            onChange={(event) => setLine(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Enter" || !sessionId || !line.trim()) return;
              const text = line;
              setLine("");
              ask({ action: "send", sessionId, text }).catch((caught: unknown) =>
                setError(caught instanceof Error ? caught.message : String(caught)),
              );
            }}
            placeholder="输入命令"
            style={fieldStyle}
            value={line}
          />
        </div>
      </div>
    </AppFrame>
  );
}
