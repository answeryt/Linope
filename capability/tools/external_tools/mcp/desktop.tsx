import { useEffect, useRef, useState } from "react";

export const appId = "mcp:MCPHub";

const hubUrl = "http://127.0.0.1:3000";

function embedded(frame: HTMLIFrameElement) {
  try {
    const href = frame.contentWindow?.location.href ?? "";
    return href !== "" && href !== "about:blank";
  } catch {
    return true;
  }
}

export default function MCPHubDesktop() {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [external, setExternal] = useState(false);
  const [popupBlocked, setPopupBlocked] = useState(false);

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    let timer = 0;
    const onLoad = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        if (embedded(frame)) return;
        const opened = window.open(hubUrl, "linope-mcphub");
        setPopupBlocked(opened === null);
        setExternal(opened !== null);
      }, 800);
    };
    frame.addEventListener("load", onLoad);
    return () => {
      frame.removeEventListener("load", onLoad);
      window.clearTimeout(timer);
    };
  }, []);

  if (external || popupBlocked) {
    return (
      <div style={{ boxSizing: "border-box", height: "100%", padding: "44px 28px 28px", color: "#1c1c1e" }}>
        <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700, lineHeight: "32px" }}>MCPHub</h1>
        <p style={{ margin: "8px 0 0", fontSize: 15, lineHeight: "22px" }}>
          {popupBlocked ? "控制台不能嵌在这个窗口里。" : "控制台已在新窗口打开。"}
        </p>
        <a href={hubUrl} rel="noreferrer" style={{ color: "#1c1c1e" }} target="_blank">
          打开 MCPHub
        </a>
      </div>
    );
  }

  return (
    <div style={{ boxSizing: "border-box", height: "100%", paddingTop: 44 }}>
      <iframe
        ref={frameRef}
        src={hubUrl}
        style={{ display: "block", width: "100%", height: "100%", border: 0, background: "transparent" }}
        title="MCPHub"
      />
    </div>
  );
}
