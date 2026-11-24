import { useEffect, useRef, type PointerEvent as ReactPointerEvent } from "react";
import { AnimatePresence, motion, type MotionValue } from "motion/react";
import { desktops } from "virtual:capability-desktops";
import { useDeferredBody } from "@/desktop/dialog/defer-body";
import { dialogGlass, dialogSurface } from "@/desktop/dialog/glass";
import { lensShadow } from "@/desktop/dialog/ChatPanel";
import { WindowControls } from "@/desktop/dialog/WindowControls";
import { useIslandActions } from "@/lib/island";

type ToolFrame = {
  left: MotionValue<number>;
  top: MotionValue<number>;
  width: MotionValue<number>;
  height: MotionValue<number>;
  textOpacity: MotionValue<number>;
  lensTop: MotionValue<number>;
  lensHeight: MotionValue<number>;
  clipPath: MotionValue<string>;
};

type Edge = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

type ResizeStart = (edge: Edge, event: ReactPointerEvent<HTMLElement>) => void;

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

const ink = "#1c1c1e";

const islandLine = {
  fontSize: 15,
  fontWeight: 600,
  lineHeight: "20px",
} as const;

const islandExpandedLine = {
  ...islandLine,
  marginLeft: 12,
};

function toolName(appId: string) {
  const index = appId.indexOf(":");
  return index === -1 ? appId : appId.slice(index + 1);
}

function frameStyle(frame: ToolFrame) {
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

function lensFrameStyle(frame: ToolFrame) {
  return {
    position: "absolute" as const,
    left: frame.left,
    top: frame.lensTop,
    width: frame.width,
    height: frame.lensHeight,
    borderRadius: dialogGlass.radius,
  };
}

function ToolLensSlot({ frame, open }: { frame: ToolFrame; open: boolean }) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div data-glass-lens key="tool-lens" style={{ ...lensFrameStyle(frame), boxShadow: lensShadow }} />
      ) : null}
    </AnimatePresence>
  );
}

function ToolBodySlot({
  appId,
  capability,
  conversations,
  frame,
  fullscreen,
  messages = [],
  onClose,
  onCreateConversation,
  onFullscreen,
  onMinimize,
  onResizeStart,
  onSelectConversation,
  open,
  process,
  selectedId,
  tasks = [],
}: {
  appId: string;
  capability?: string;
  conversations?: Array<{
    id: string;
    pid: string;
    queued: number;
    running: boolean;
  }>;
  frame: ToolFrame;
  fullscreen: boolean;
  messages?: Array<{
    id: string;
    reasoning?: string;
    role: "assistant" | "error" | "system" | "user";
    stream?: boolean;
    text: string;
  }>;
  onClose: () => void;
  onCreateConversation?: () => void;
  onFullscreen: () => void;
  onMinimize: () => void;
  onResizeStart: ResizeStart;
  onSelectConversation?: (id: string) => void;
  open: boolean;
  selectedId?: string;
  process?: {
    activity: "away" | "busy" | "waiting";
    capability: string;
    id: string;
  } | null;
  tasks?: Array<{
    id: string;
    leader: boolean;
    pc: string;
    pid: string;
    registers: Record<string, unknown>;
  }>;
}) {
  const Desktop = desktops[appId];
  const label = toolName(appId);
  const bodyReady = useDeferredBody(open);
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          aria-label={label}
          className="pointer-events-auto absolute overflow-hidden"
          key="tool-window"
          role="dialog"
          style={{ ...frameStyle(frame), ...dialogSurface }}
        >
          <motion.div
            className="relative z-0 h-full w-full"
            onWheel={(event) => event.stopPropagation()}
            style={{ color: ink, opacity: frame.textOpacity }}
          >
            {bodyReady ? (
              Desktop ? (
                <Desktop
                  capability={capability}
                  conversations={conversations}
                  messages={messages}
                  onCreateConversation={onCreateConversation}
                  onSelectConversation={onSelectConversation}
                  process={process}
                  selectedId={selectedId}
                  tasks={tasks}
                />
              ) : (
                <MissingTool name={label} />
              )
            ) : null}
          </motion.div>
          <ResizeEdges onResizeStart={onResizeStart} />
          <WindowControls
            fullscreen={fullscreen}
            minimized={false}
            onClose={onClose}
            onFullscreen={onFullscreen}
            onMinimize={onMinimize}
          />
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function MissingTool({ name }: { name: string }) {
  return (
    <div style={{ boxSizing: "border-box", height: "100%", padding: "44px 28px 28px" }}>
      <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700, lineHeight: "32px" }}>{name}</h1>
      <p style={{ margin: "8px 0 0", fontSize: 15, lineHeight: "22px" }}>这个工具还没有界面。</p>
    </div>
  );
}

function ToolIsland({
  active,
  appId,
  onRestore,
}: {
  active: boolean;
  appId: string | null;
  onRestore: () => void;
}) {
  const island = useIslandActions();
  const restore = useRef(onRestore);
  restore.current = onRestore;
  const name = appId ? toolName(appId) : "应用";

  useEffect(() => {
    if (!active) return;
    const handle = island.start({
      id: "tool",
      label: `应用，${name}`,
      onPress: () => {
        if (island.presentation === "expanded") {
          restore.current();
          return;
        }
        island.expand("tool");
      },
      compact: { leading: <span style={islandLine}>{name}</span> },
      minimal: <span style={islandLine}>{name}</span>,
      expanded: {
        leading: <span style={islandExpandedLine}>{name}</span>,
        bottom: <span style={{ ...islandExpandedLine, opacity: 0.62 }}>已打开的应用</span>,
      },
    });
    return () => handle.end();
  }, [active, island, name]);

  return null;
}

function ResizeEdges({ onResizeStart }: { onResizeStart: ResizeStart }) {
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

export { ToolBodySlot, ToolIsland, ToolLensSlot };
