import { useState } from "react";
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

export const appId = "code:运行代码";

export default function CodeDesktop({ call, cwd = "" }: { call?: CapabilityCaller; cwd?: string }) {
  const [code, setCode] = useState("return 1 + 1");
  const [logs, setLogs] = useState("");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [ran, setRan] = useState(false);

  return (
    <AppFrame>
      <div style={{ alignItems: "center", display: "flex", gap: 8 }}>
        <span style={{ flex: 1, fontSize: 15, fontWeight: 650, lineHeight: "22px" }}>运行代码</span>
        <button
          onClick={() => {
            if (!call) {
              setError("当前没有连上内核，不能直接操作。");
              return;
            }
            const description = code.split("\n").map((line) => line.trim()).find(Boolean) || "运行这段程序";
            setError("");
            runCall(call, {
              body: { code, description, timeoutMs: 60000 },
              capability: "tools.run_code",
              cwd,
              hold: true,
              kind: "tool",
            })
              .then((payload) => {
                const printed = Array.isArray(payload.logs) ? payload.logs.map((item) => String(item)).join("\n") : "";
                setLogs(printed);
                setResult(payload.result === undefined ? "" : JSON.stringify(payload.result, null, 2));
                setRan(true);
              })
              .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : String(caught)));
          }}
          style={buttonStyle}
          type="button"
        >
          运行
        </button>
      </div>
      <ErrorLine>{error}</ErrorLine>
      <div style={{ display: "flex", flex: 1, gap: 10, minHeight: 0 }}>
        <textarea
          aria-label="程序"
          onChange={(event) => setCode(event.target.value)}
          spellCheck={false}
          style={{
            ...fieldStyle,
            ...cardStyle,
            flex: 1,
            fontFamily: "ui-monospace, Consolas, monospace",
            minHeight: 0,
            resize: "none",
          }}
          value={code}
        />
        <div style={{ ...cardStyle, display: "flex", flex: 1, flexDirection: "column", gap: 8, minHeight: 0, overflow: "auto", padding: 12 }}>
          {!ran ? <EmptyPane>运行之后，打印和返回值会出现在这里。</EmptyPane> : null}
          {logs ? (
            <pre style={{ color: ink, fontFamily: "ui-monospace, Consolas, monospace", fontSize: 13, lineHeight: "18px", margin: 0, whiteSpace: "pre-wrap" }}>
              {logs}
            </pre>
          ) : null}
          {ran ? (
            <p style={{ color: quiet, fontSize: 13, lineHeight: "18px", margin: 0 }}>
              返回值 {result || "空"}
            </p>
          ) : null}
        </div>
      </div>
    </AppFrame>
  );
}
