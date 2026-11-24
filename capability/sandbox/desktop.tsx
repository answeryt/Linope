export const appId = "sandbox:沙盒工具";

export default function SandboxDesktop() {
  return (
    <div style={{ boxSizing: "border-box", height: "100%", padding: "44px 28px 28px", color: "#1c1c1e" }}>
      <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700, lineHeight: "32px" }}>沙盒工具</h1>
      <p style={{ margin: "8px 0 0", fontSize: 15, lineHeight: "22px" }}>在隔离环境中运行代码、访问文件并测试想法。</p>
    </div>
  );
}
