import type { CSSProperties, ReactNode } from "react";

const ink = "#1c1c1e";
const quiet = "rgba(60, 60, 67, 0.72)";

const cardStyle: CSSProperties = {
  background: "rgba(255,255,255,0.55)",
  border: "1px solid rgba(255,255,255,0.88)",
  borderRadius: 14,
};

const fieldStyle: CSSProperties = {
  background: "rgba(255,255,255,0.72)",
  border: 0,
  borderRadius: 12,
  color: ink,
  fontSize: 14,
  lineHeight: "20px",
  outline: "none",
  padding: "8px 12px",
  width: "100%",
};

const buttonStyle: CSSProperties = {
  background: "rgba(255,255,255,0.82)",
  border: 0,
  borderRadius: 999,
  color: ink,
  cursor: "pointer",
  flex: "0 0 auto",
  fontSize: 13,
  lineHeight: "18px",
  padding: "6px 12px",
};

type CapabilityCallInput = {
  capability: string;
  kind: "tool" | "sandbox";
  body: Record<string, unknown>;
  hold?: boolean;
  cwd?: string;
};

type CapabilityCaller = (input: CapabilityCallInput) => Promise<unknown>;

function AppFrame({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        boxSizing: "border-box",
        color: ink,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        height: "100%",
        minHeight: 0,
        padding: "44px 16px 16px",
      }}
    >
      {children}
    </div>
  );
}

function EmptyPane({ children }: { children: ReactNode }) {
  return <p style={{ color: quiet, fontSize: 15, lineHeight: "22px", margin: 0 }}>{children}</p>;
}

function ErrorLine({ children }: { children: ReactNode }) {
  if (!children) return null;
  return <p style={{ color: "#8b1e2d", fontSize: 13, lineHeight: "18px", margin: 0 }}>{children}</p>;
}

function readCallResult(result: unknown): Record<string, unknown> {
  if (typeof result === "string") {
    try {
      const parsed: unknown = JSON.parse(result);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      return { error: result, success: false };
    }
  }
  if (result && typeof result === "object" && !Array.isArray(result)) {
    return result as Record<string, unknown>;
  }
  return { error: "没有返回结果", success: false };
}

function callFailure(payload: Record<string, unknown>): string {
  if (payload.success === false) return String(payload.error || "没有完成");
  return "";
}

async function runCall(call: CapabilityCaller, input: CapabilityCallInput) {
  const payload = readCallResult(await call(input));
  const failure = callFailure(payload);
  if (failure) throw new Error(failure);
  return payload;
}

export type { CapabilityCallInput, CapabilityCaller };
export { AppFrame, EmptyPane, ErrorLine, buttonStyle, cardStyle, fieldStyle, ink, quiet, runCall };
