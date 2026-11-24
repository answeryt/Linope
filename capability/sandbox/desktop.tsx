import { useEffect, useState } from "react";
import {
  AppFrame,
  ErrorLine,
  cardStyle,
  ink,
  quiet,
  runCall,
  type CapabilityCaller,
} from "@/desktop/apps/shell";

export const appId = "sandbox:沙盒工具";

const modes = [
  { detail: "可以读，不能改。", id: "read-only", name: "只查看" },
  { detail: "可以改工作目录和临时目录。", id: "workspace-write", name: "工作文件夹可写" },
  { detail: "不再套一层限制。", id: "danger-full-access", name: "完全访问" },
];

function linesOf(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item)).filter(Boolean);
}

export default function SandboxDesktop({ call, cwd = "" }: { call?: CapabilityCaller; cwd?: string }) {
  const [mode, setMode] = useState(modes[1].id);
  const [roots, setRoots] = useState<string[]>([]);
  const [writable, setWritable] = useState<string[]>([]);
  const [blocked, setBlocked] = useState<string[]>([]);
  const [error, setError] = useState("");

  function load(next: string) {
    if (!call) {
      setError("当前没有连上内核，不能直接操作。");
      return;
    }
    setMode(next);
    setError("");
    runCall(call, {
      body: { cwd, mode: next, scope: "host" },
      capability: "sandbox.sandbox",
      cwd,
      hold: true,
      kind: "sandbox",
    })
      .then((payload) => {
        setRoots(linesOf(payload.roots));
        setWritable(linesOf(payload.writable_roots));
        setBlocked(linesOf(payload.blocked_names));
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : String(caught)));
  }

  useEffect(() => {
    load(modes[1].id);
  }, [call, cwd]);

  return (
    <AppFrame>
      <div style={{ display: "flex", gap: 8 }}>
        {modes.map((item) => (
          <button
            key={item.id}
            onClick={() => load(item.id)}
            style={{
              ...cardStyle,
              background: item.id === mode ? "rgba(255,255,255,0.82)" : cardStyle.background,
              color: ink,
              cursor: "pointer",
              flex: 1,
              padding: "12px 14px",
              textAlign: "left",
            }}
            type="button"
          >
            <span style={{ display: "block", fontSize: 15, fontWeight: 650, lineHeight: "22px" }}>{item.name}</span>
            <span style={{ color: quiet, display: "block", fontSize: 13, lineHeight: "18px" }}>{item.detail}</span>
          </button>
        ))}
      </div>
      <ErrorLine>{error}</ErrorLine>
      <div style={{ ...cardStyle, flex: 1, minHeight: 0, overflow: "auto", padding: 14 }}>
        <p style={{ fontSize: 13, lineHeight: "18px", margin: "0 0 8px" }}>
          这是当前目录下这份范围。文件和终端仍用它们自己声明的范围。
        </p>
        <Section title="根目录" values={roots} />
        <Section title="可写" values={writable} />
        <Section title="挡住的名字" values={blocked} />
      </div>
    </AppFrame>
  );
}

function Section({ title, values }: { title: string; values: string[] }) {
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 13, fontWeight: 650, lineHeight: "18px" }}>{title}</div>
      {values.length === 0 ? (
        <div style={{ color: quiet, fontSize: 14, lineHeight: "20px" }}>没有</div>
      ) : (
        values.map((value) => (
          <div key={value} style={{ fontSize: 14, lineHeight: "20px" }}>
            {value}
          </div>
        ))
      )}
    </div>
  );
}
