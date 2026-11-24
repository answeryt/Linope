export const appId = "file:文件";

export default function FileDesktop() {
  return (
    <div style={{ boxSizing: "border-box", height: "100%", padding: "44px 28px 28px", color: "#1c1c1e" }}>
      <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700, lineHeight: "32px" }}>文件</h1>
      <p style={{ margin: "8px 0 0", fontSize: 15, lineHeight: "22px" }}>文件读写、编辑和目录访问。</p>
    </div>
  );
}
