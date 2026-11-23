import { useState } from "react";

const lights = [
  { id: "close", color: "#ff5f57", label: "关闭" },
  { id: "minimize", color: "#febc2e", label: "最小化" },
  { id: "zoom", color: "#28c840", label: "全屏" },
] as const;

function WindowControls({
  fullscreen,
  minimized,
  onClose,
  onFullscreen,
  onMinimize,
  variant = "corner",
}: {
  fullscreen: boolean;
  minimized: boolean;
  onClose: () => void;
  onFullscreen: () => void;
  onMinimize: () => void;
  variant?: "corner" | "inline";
}) {
  const [hot, setHot] = useState(false);
  const actions = {
    close: onClose,
    minimize: onMinimize,
    zoom: onFullscreen,
  };
  const labels = {
    close: "关闭",
    minimize: minimized ? "还原" : "最小化",
    zoom: fullscreen ? "退出全屏" : "全屏",
  };

  return (
    <div
      className={
        variant === "inline"
          ? "flex items-center gap-2"
          : "absolute right-4 top-4 z-20 flex items-center gap-2"
      }
      style={variant === "inline" ? { pointerEvents: "auto" } : undefined}
      onBlur={() => setHot(false)}
      onFocus={() => setHot(true)}
      onMouseEnter={() => setHot(true)}
      onMouseLeave={() => setHot(false)}
      onPointerDown={(event) => event.stopPropagation()}
    >
      {lights.map((light) => (
        <button
          aria-label={labels[light.id]}
          className="grid cursor-pointer place-items-center border-0 p-0"
          key={light.id}
          onClick={actions[light.id]}
          style={{
            width: 12,
            height: 12,
            borderRadius: 999,
            background: light.color,
            boxShadow: "inset 0 0 0 0.5px rgba(0,0,0,0.18)",
            color: "rgba(0,0,0,0.55)",
            outline: "none",
          }}
          type="button"
        >
          {hot ? <LightIcon id={light.id} fullscreen={fullscreen} /> : null}
        </button>
      ))}
    </div>
  );
}

function LightIcon({ id, fullscreen }: { id: (typeof lights)[number]["id"]; fullscreen: boolean }) {
  if (id === "close") {
    return (
      <svg aria-hidden="true" height="7" viewBox="0 0 8 8" width="7">
        <path d="M1.6 1.6l4.8 4.8M6.4 1.6L1.6 6.4" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.2" />
      </svg>
    );
  }
  if (id === "minimize") {
    return (
      <svg aria-hidden="true" height="7" viewBox="0 0 8 8" width="7">
        <path d="M1.5 4h5" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.2" />
      </svg>
    );
  }
  return fullscreen ? <RestoreIcon /> : <ExpandIcon />;
}

function ExpandIcon() {
  return (
    <svg aria-hidden="true" height="7" viewBox="0 0 8 8" width="7">
      <path
        d="M1.2 3V1.2H3M5 1.2h1.8V3M6.8 5v1.8H5M3 6.8H1.2V5"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.1"
      />
    </svg>
  );
}

function RestoreIcon() {
  return (
    <svg aria-hidden="true" height="7" viewBox="0 0 8 8" width="7">
      <path
        d="M3 1.2v1.8H1.2M5 1.2v1.8h1.8M6.8 5v1.8H5M1.2 5v1.8H3"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.1"
      />
    </svg>
  );
}

export { WindowControls };
