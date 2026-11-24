export const appId = "loop:pi";

export default function PiDesktop() {
  return (
    <div style={{ boxSizing: "border-box", height: "100%", padding: "44px 28px 28px", color: "#1c1c1e" }}>
      <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700, lineHeight: "32px" }}>pi</h1>
      <p style={{ margin: "8px 0 0", fontSize: 15, lineHeight: "22px" }}>
        换上 Pi 的循环。问模型仍写 model use 和 model run，工具仍用 process start 和 load tool。
      </p>
    </div>
  );
}
