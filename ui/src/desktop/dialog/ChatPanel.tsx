import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import {
  animate,
  AnimatePresence,
  motion,
  useMotionValue,
  useTransform,
  type MotionValue,
} from "motion/react";
import type { UiTurn } from "@/desktop/link/state";
import { ChatBubbles } from "@/desktop/dialog/ChatBubbles";
import { dialogGlass, dialogSurface } from "@/desktop/dialog/glass";
import { WindowControls } from "@/desktop/dialog/WindowControls";
import { useIslandActions } from "@/lib/island";

const PANEL_GAP = 18;
const PANEL_MARGIN = 28;
const MIN_WIDTH = 360;
const MIN_HEIGHT = 220;
const PANEL_SPRING = { type: "spring" as const, visualDuration: 0.55, bounce: 0.2 };
const TEXT_FADE = { duration: 0.28, ease: [0.22, 1, 0.36, 1] as const };
const WIPE = { duration: 0.62, ease: [0.22, 1, 0.36, 1] as const };
const WAVE = 14;

const lensShadow =
  "inset 0 1px 1.5px rgba(255,255,255,0.55), 0 22px 48px -18px rgba(0,0,0,0.45)";

type ChatMessage = UiTurn;

type Rect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type ChatFrame = {
  left: MotionValue<number>;
  top: MotionValue<number>;
  width: MotionValue<number>;
  height: MotionValue<number>;
  textOpacity: MotionValue<number>;
  lensTop: MotionValue<number>;
  lensHeight: MotionValue<number>;
  clipPath: MotionValue<string>;
};

type Mode = "idle" | "opening" | "normal" | "min" | "full";
type Edge = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

const edges: Edge[] = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];

const edgeLabel: Record<Edge, string> = {
  n: "调整上边缘",
  s: "调整下边缘",
  e: "调整右边缘",
  w: "调整左边缘",
  ne: "调整右上角",
  nw: "调整左上角",
  se: "调整右下角",
  sw: "调整左下角",
};

const edgeStyle: Record<Edge, { cursor: string; style: Record<string, number | string> }> = {
  n: { cursor: "ns-resize", style: { top: 0, left: 14, right: 14, height: 8 } },
  s: { cursor: "ns-resize", style: { bottom: 0, left: 14, right: 14, height: 8 } },
  e: { cursor: "ew-resize", style: { top: 14, right: 0, bottom: 14, width: 8 } },
  w: { cursor: "ew-resize", style: { top: 14, left: 0, bottom: 14, width: 8 } },
  ne: { cursor: "nesw-resize", style: { top: 0, right: 0, width: 14, height: 14 } },
  nw: { cursor: "nwse-resize", style: { top: 0, left: 0, width: 14, height: 14 } },
  se: { cursor: "nwse-resize", style: { right: 0, bottom: 0, width: 14, height: 14 } },
  sw: { cursor: "nesw-resize", style: { left: 0, bottom: 0, width: 14, height: 14 } },
};

function bounds() {
  const viewW = window.innerWidth;
  const viewH = window.innerHeight;
  const barTop = viewH - dialogGlass.bottom - dialogGlass.height;
  const areaTop = PANEL_MARGIN;
  const areaBottom = barTop - PANEL_GAP;
  const areaLeft = 24;
  const areaRight = viewW - 24;
  return {
    viewW,
    areaTop,
    areaBottom,
    areaLeft,
    areaRight,
    areaWidth: Math.max(dialogGlass.width, areaRight - areaLeft),
    areaHeight: Math.max(dialogGlass.height, areaBottom - areaTop),
    barTop,
  };
}

function defaultRect(): Rect {
  const area = bounds();
  const width = Math.min(dialogGlass.panelWidth, area.areaWidth);
  const height = Math.min(dialogGlass.panelHeight, area.areaHeight);
  return {
    left: area.areaLeft + (area.areaWidth - width) / 2,
    top: area.areaTop + (area.areaHeight - height) / 2,
    width,
    height,
  };
}

function liquidClip(progress: number): string {
  const amount = Math.min(1, Math.max(0, progress));
  if (amount <= 0.001) return `inset(0 round ${dialogGlass.radius}px)`;
  const base = -WAVE + amount * (100 + WAVE * 2);
  const steps = 10;
  const edge: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const x = (i / steps) * 100;
    const bulge = Math.sin((i / steps) * Math.PI) * WAVE;
    edge.push(`${x}% ${base + bulge}%`);
  }
  return `polygon(${edge.join(", ")}, 100% 100%, 0% 100%)`;
}

function clearedAmount(progress: number): number {
  const amount = Math.min(1, Math.max(0, progress));
  const tip = (-WAVE + amount * (100 + WAVE * 2) + WAVE) / 100;
  return Math.min(1, Math.max(0, tip));
}

function fullscreenRect(): Rect {
  const area = bounds();
  return {
    left: area.areaLeft,
    top: area.areaTop,
    width: area.areaWidth,
    height: area.areaHeight,
  };
}

function clampIntoView(rect: Rect): Rect {
  const area = bounds();
  const minWidth = Math.min(MIN_WIDTH, area.areaWidth);
  const minHeight = Math.min(MIN_HEIGHT, area.areaHeight);
  const width = Math.min(Math.max(rect.width, minWidth), area.areaWidth);
  const height = Math.min(Math.max(rect.height, minHeight), area.areaHeight);
  let left = rect.left;
  let top = rect.top;
  if (left < area.areaLeft) left = area.areaLeft;
  if (top < area.areaTop) top = area.areaTop;
  if (left + width > area.areaRight) left = Math.max(area.areaLeft, area.areaRight - width);
  if (top + height > area.areaBottom) top = Math.max(area.areaTop, area.areaBottom - height);
  return { left, top, width, height };
}

function resizeBy(edge: Edge, start: Rect, dx: number, dy: number): Rect {
  const area = bounds();
  const minWidth = Math.min(MIN_WIDTH, area.areaWidth);
  const minHeight = Math.min(MIN_HEIGHT, area.areaHeight);
  let left = start.left;
  let top = start.top;
  let right = start.left + start.width;
  let bottom = start.top + start.height;
  if (edge.includes("e")) right += dx;
  if (edge.includes("w")) left += dx;
  if (edge.includes("s")) bottom += dy;
  if (edge.includes("n")) top += dy;
  if (right - left < minWidth) {
    if (edge.includes("w") && !edge.includes("e")) left = right - minWidth;
    else right = left + minWidth;
  }
  if (bottom - top < minHeight) {
    if (edge.includes("n") && !edge.includes("s")) top = bottom - minHeight;
    else bottom = top + minHeight;
  }
  if (left < area.areaLeft) {
    if (edge.includes("e") && !edge.includes("w")) right -= area.areaLeft - left;
    left = area.areaLeft;
  }
  if (right > area.areaRight) {
    if (edge.includes("w") && !edge.includes("e")) left -= right - area.areaRight;
    right = area.areaRight;
  }
  if (top < area.areaTop) {
    if (edge.includes("s") && !edge.includes("n")) bottom -= area.areaTop - top;
    top = area.areaTop;
  }
  if (bottom > area.areaBottom) {
    if (edge.includes("n") && !edge.includes("s")) top -= bottom - area.areaBottom;
    bottom = area.areaBottom;
  }
  return { left, top, width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
}

function useChatFrame(open: boolean, reduced: boolean) {
  const left = useMotionValue(0);
  const top = useMotionValue(0);
  const width = useMotionValue(dialogGlass.width);
  const height = useMotionValue(dialogGlass.height);
  const textOpacity = useMotionValue(0);
  const reveal = useMotionValue(0);
  const lensTop = useTransform([top, height, reveal], ([y, h, progress]) => {
    return Number(y) + Number(h) * clearedAmount(Number(progress));
  });
  const lensHeight = useTransform([height, reveal], ([h, progress]) => {
    return Math.max(0, Number(h) * (1 - clearedAmount(Number(progress))));
  });
  const clipPath = useTransform(reveal, liquidClip);
  const wasOpen = useRef(false);
  const closingRef = useRef(false);
  const normalRef = useRef<Rect | null>(null);
  const userSizedRef = useRef(false);
  const wasFullRef = useRef(false);
  const modeRef = useRef<Mode>("idle");
  const controlsRef = useRef<Array<{ stop: () => void }>>([]);
  const revealControl = useRef<{ stop: () => void } | null>(null);
  const revealRun = useRef(0);
  const runRef = useRef(0);
  const reducedRef = useRef(reduced);
  const [mode, setMode] = useState<Mode>("idle");
  reducedRef.current = reduced;
  modeRef.current = mode;

  if (typeof window !== "undefined" && open && !wasOpen.current) {
    const target = clampIntoView(
      userSizedRef.current && normalRef.current ? normalRef.current : defaultRect(),
    );
    left.jump(target.left);
    top.jump(target.top);
    width.jump(target.width);
    height.jump(target.height);
    textOpacity.jump(1);
  }
  wasOpen.current = open;

  const readRect = (): Rect => ({
    left: left.get(),
    top: top.get(),
    width: width.get(),
    height: height.get(),
  });

  const jumpRect = (rect: Rect) => {
    left.jump(rect.left);
    top.jump(rect.top);
    width.jump(rect.width);
    height.jump(rect.height);
  };

  const halt = () => {
    runRef.current += 1;
    for (const control of controlsRef.current) {
      control.stop();
    }
    controlsRef.current = [];
  };

  const springTo = (rect: Rect, fade: boolean, onDone?: () => void) => {
    halt();
    const id = runRef.current;
    if (reducedRef.current) {
      jumpRect(rect);
      textOpacity.jump(1);
      onDone?.();
      return;
    }
    const motion = [
      animate(left, rect.left, {
        ...PANEL_SPRING,
        onComplete: () => {
          if (id !== runRef.current) {
            return;
          }
          onDone?.();
        },
      }),
      animate(top, rect.top, PANEL_SPRING),
      animate(width, rect.width, PANEL_SPRING),
      animate(height, rect.height, PANEL_SPRING),
    ];
    if (fade) {
      motion.push(animate(textOpacity, 1, TEXT_FADE));
    }
    controlsRef.current = motion;
  };

  const playReveal = (to: number, onDone?: () => void) => {
    revealRun.current += 1;
    revealControl.current?.stop();
    const id = revealRun.current;
    if (reducedRef.current) {
      reveal.jump(to);
      onDone?.();
      return;
    }
    revealControl.current = animate(reveal, to, {
      ...WIPE,
      onComplete: () => {
        if (id !== revealRun.current) {
          return;
        }
        onDone?.();
      },
    });
  };

  useLayoutEffect(() => {
    if (!open || typeof window === "undefined") {
      modeRef.current = "idle";
      wasFullRef.current = false;
      closingRef.current = false;
      revealRun.current += 1;
      revealControl.current?.stop();
      reveal.jump(0);
      if (mode !== "idle") {
        setMode("idle");
      }
      return;
    }
    const target = clampIntoView(
      userSizedRef.current && normalRef.current ? normalRef.current : defaultRect(),
    );
    jumpRect(target);
    textOpacity.jump(1);
    reveal.jump(reducedRef.current ? 0 : 1);
    modeRef.current = "opening";
    playReveal(0, () => {
      if (modeRef.current !== "opening") {
        return;
      }
      modeRef.current = "normal";
      setMode("normal");
    });
    const onResize = () => {
      const current = modeRef.current;
      if (current === "full") {
        jumpRect(fullscreenRect());
        return;
      }
      if (current === "min") {
        if (normalRef.current) {
          normalRef.current = clampIntoView(normalRef.current);
        }
        return;
      }
      const next = clampIntoView(
        userSizedRef.current && normalRef.current ? normalRef.current : defaultRect(),
      );
      if (current === "opening" || closingRef.current) {
        jumpRect(next);
        return;
      }
      if (userSizedRef.current) {
        normalRef.current = next;
      }
      jumpRect(next);
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
    };
  }, [open, reduced]);

  const close = (onDone: () => void) => {
    if (closingRef.current) {
      return;
    }
    closingRef.current = true;
    playReveal(1, () => {
      closingRef.current = false;
      onDone();
    });
  };

  const toggleMinimize = () => {
    if (closingRef.current) {
      return;
    }
    if (modeRef.current === "min") {
      const back = wasFullRef.current
        ? fullscreenRect()
        : clampIntoView(normalRef.current ?? defaultRect());
      jumpRect(back);
      reveal.jump(reducedRef.current ? 0 : 1);
      modeRef.current = wasFullRef.current ? "full" : "normal";
      setMode(modeRef.current);
      playReveal(0);
      return;
    }
    wasFullRef.current = modeRef.current === "full";
    if (!wasFullRef.current) {
      normalRef.current = readRect();
    }
    modeRef.current = "min";
    setMode("min");
  };

  const toggleFullscreen = () => {
    if (closingRef.current) {
      return;
    }
    reveal.jump(0);
    if (modeRef.current === "full") {
      wasFullRef.current = false;
      modeRef.current = "normal";
      setMode("normal");
      springTo(clampIntoView(normalRef.current ?? defaultRect()), false);
      return;
    }
    if (modeRef.current === "min") {
      wasFullRef.current = true;
      modeRef.current = "full";
      setMode("full");
      springTo(fullscreenRect(), false);
      return;
    }
    normalRef.current = readRect();
    wasFullRef.current = true;
    modeRef.current = "full";
    setMode("full");
    springTo(fullscreenRect(), false);
  };

  const restoreIfMinimized = () => {
    if (modeRef.current !== "min") {
      return;
    }
    toggleMinimize();
  };

  const startResize = (edge: Edge, event: ReactPointerEvent<HTMLElement>) => {
    if (modeRef.current === "min" || closingRef.current) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    halt();
    const start = readRect();
    const originX = event.clientX;
    const originY = event.clientY;
    const move = (ev: PointerEvent) => {
      jumpRect(resizeBy(edge, start, ev.clientX - originX, ev.clientY - originY));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      if (modeRef.current !== "full") {
        userSizedRef.current = true;
        normalRef.current = readRect();
        modeRef.current = "normal";
        setMode("normal");
      }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  return {
    frame: { left, top, width, height, textOpacity, lensTop, lensHeight, clipPath },
    fullscreen: mode === "full",
    minimized: mode === "min",
    close,
    restoreIfMinimized,
    startResize,
    toggleFullscreen,
    toggleMinimize,
  };
}

function frameStyle(frame: ChatFrame) {
  return {
    position: "absolute" as const,
    left: frame.left,
    top: frame.top,
    width: frame.width,
    height: frame.height,
    borderRadius: dialogGlass.radius,
    clipPath: frame.clipPath,
  };
}

function lensFrameStyle(frame: ChatFrame) {
  return {
    position: "absolute" as const,
    left: frame.left,
    top: frame.lensTop,
    width: frame.width,
    height: frame.lensHeight,
    borderRadius: dialogGlass.radius,
  };
}

function ChatLens({ frame }: { frame: ChatFrame }) {
  return (
    <motion.div
      data-glass-lens
      style={{
        ...lensFrameStyle(frame),
        boxShadow: lensShadow,
      }}
    />
  );
}

function ResizeEdges({
  onResizeStart,
}: {
  onResizeStart: (edge: Edge, event: ReactPointerEvent<HTMLElement>) => void;
}) {
  return (
    <>
      {edges.map((edge) => (
        <div
          aria-label={edgeLabel[edge]}
          key={edge}
          onPointerDown={(event) => onResizeStart(edge, event)}
          role="separator"
          style={{
            position: "absolute",
            zIndex: 10,
            touchAction: "none",
            cursor: edgeStyle[edge].cursor,
            ...edgeStyle[edge].style,
          }}
        />
      ))}
    </>
  );
}

function ChatTranscript({
  frame,
  fullscreen,
  messages,
  minimized,
  running,
  onClose,
  onFullscreen,
  onMinimize,
  onResizeStart,
  reduced,
}: {
  frame: ChatFrame;
  fullscreen: boolean;
  messages: ChatMessage[];
  minimized: boolean;
  running: boolean;
  onClose: () => void;
  onFullscreen: () => void;
  onMinimize: () => void;
  onResizeStart: (edge: Edge, event: ReactPointerEvent<HTMLElement>) => void;
  reduced: boolean;
}) {
  return (
    <motion.div
      className="pointer-events-auto absolute overflow-hidden"
      style={{ ...frameStyle(frame), ...dialogSurface, zIndex: 25 }}
    >
      {minimized ? null : (
        <ChatBubbles
          messages={messages}
          reduced={reduced}
          running={running}
          style={{ opacity: frame.textOpacity }}
        />
      )}
      {minimized ? null : <ResizeEdges onResizeStart={onResizeStart} />}
      <WindowControls
        fullscreen={fullscreen}
        minimized={minimized}
        onClose={onClose}
        onFullscreen={onFullscreen}
        onMinimize={onMinimize}
      />
    </motion.div>
  );
}

function ChatLensSlot({ frame, open }: { frame: ChatFrame; open: boolean }) {
  return (
    <AnimatePresence>
      {open ? <ChatLens frame={frame} key="chat-lens" /> : null}
    </AnimatePresence>
  );
}

function ChatTranscriptSlot({
  frame,
  fullscreen,
  messages,
  minimized,
  running,
  onClose,
  onFullscreen,
  onMinimize,
  onResizeStart,
  open,
  reduced,
}: {
  frame: ChatFrame;
  fullscreen: boolean;
  messages: ChatMessage[];
  minimized: boolean;
  running: boolean;
  onClose: () => void;
  onFullscreen: () => void;
  onMinimize: () => void;
  onResizeStart: (edge: Edge, event: ReactPointerEvent<HTMLElement>) => void;
  open: boolean;
  reduced: boolean;
}) {
  return (
    <AnimatePresence>
      {open ? (
        <ChatTranscript
          frame={frame}
          fullscreen={fullscreen}
          key="chat-transcript"
          messages={messages}
          minimized={minimized}
          running={running}
          onClose={onClose}
          onFullscreen={onFullscreen}
          onMinimize={onMinimize}
          onResizeStart={onResizeStart}
          reduced={reduced}
        />
      ) : null}
    </AnimatePresence>
  );
}

const islandLine = {
  fontSize: 15,
  fontWeight: 600,
  lineHeight: "20px",
} as const;

// The expanded island clips its upper-left corner, so the first stroke sits on the cut.
const islandExpandedLine = {
  ...islandLine,
  marginLeft: 12,
};

function ChatIsland({
  active,
  detail,
  onRestore,
}: {
  active: boolean;
  detail: string;
  onRestore: () => void;
}) {
  const island = useIslandActions();
  const restore = useRef(onRestore);
  restore.current = onRestore;

  useEffect(() => {
    if (!active) {
      return;
    }
    const handle = island.start({
      id: "chat",
      label: `对话，${detail}`,
      onPress: () => {
        if (island.presentation === "expanded") {
          restore.current();
          return;
        }
        island.expand("chat");
      },
      compact: {
        leading: <span style={islandLine}>对话</span>,
      },
      minimal: <span style={islandLine}>对话</span>,
      expanded: {
        leading: <span style={islandExpandedLine}>对话</span>,
        bottom: <span style={{ ...islandExpandedLine, opacity: 0.62 }}>{detail}</span>,
      },
    });
    return () => handle.end();
  }, [active, island]);

  useEffect(() => {
    if (!active) {
      return;
    }
    island.update("chat", {
      label: `对话，${detail}`,
      expanded: {
        bottom: <span style={{ ...islandExpandedLine, opacity: 0.62 }}>{detail}</span>,
      },
    });
  }, [active, detail, island]);

  return null;
}

export { ChatIsland, ChatLensSlot, ChatTranscriptSlot, lensShadow, useChatFrame };
export type { ChatMessage };
