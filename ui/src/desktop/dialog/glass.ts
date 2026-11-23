// 对话框的玻璃参数。改这里的数字即可，不用动组件。
const dialogGlass = {
  width: 240,
  height: 64,
  expandedWidth: 400,
  expandedHeight: 64,
  maxWidth: 520,
  maxHeight: 160,
  panelWidth: 760,
  panelHeight: 640,
  bottom: 22,
  radius: 32,
  tint: 0.98,
  tintColor: "255,255,255",
  tintBlur: 49,
  blur: 0.25,
  depth: 10,
  domeDepth: 12,
  scale: 0.12,
  chroma: 0.2,
  edgeHighlight: 0.4,
  glow: 0.16,
};

const dialogSurface = {
  background: "rgba(255,255,255,0.34)",
  backdropFilter: "blur(24px) saturate(1.25)",
  WebkitBackdropFilter: "blur(24px) saturate(1.25)",
} as const;

export { dialogGlass, dialogSurface };
