import { type CSSProperties, type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Glass } from "@/components/ui/glass";
import {
  PRESS_DURATION,
  prefersReducedMotion,
  RELEASE_DURATION,
} from "@/components/ui/glass-motion";
import {
  ChatIsland,
  ChatLensSlot,
  ChatTranscriptSlot,
  lensShadow,
  useChatFrame,
} from "@/desktop/dialog/ChatPanel";
import { dialogGlass, dialogSurface } from "@/desktop/dialog/glass";
import { SettingsBodySlot, SettingsIsland, SettingsLensSlot } from "@/desktop/setting/SettingsPanel";
import { AppsBodySlot, AppsIsland, AppsLensSlot } from "@/desktop/apps/AppsPanel";
import { ToolBodySlot, ToolIsland, ToolLensSlot } from "@/desktop/apps/HostedAppWindow";
import { EdgeSidebar } from "@/desktop/apps/EdgeSidebar";
import { useKernelSession } from "@/desktop/link/useKernelSession";
import { hostedMessages } from "@/desktop/link/state";
import { loopAppId, routeDraft } from "@/desktop/link/route";
import { useSettings } from "@/desktop/setting/settings";
import { loops } from "virtual:capability-desktops";
import allAppsIcon from "@/desktop/apps/全部_all-application.svg";
import settingIcon from "@/desktop/setting/设置_setting-two.svg";

const PRESS_EASE = "cubic-bezier(0.22, 1.15, 0.36, 1.06)";
const LINE_HEIGHT = 20;
const TEXT_PAD = 10;
const RAIL_WIDTH = 45;

const railApps = [
  { id: "settings", label: "设置", icon: settingIcon },
  { id: "all", label: "全部应用", icon: allAppsIcon },
];

function Dialog({ children }: { children: ReactNode }) {
  const glass = dialogGlass;
  const barRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const railRef = useRef<HTMLDivElement>(null);
  const railWheelRef = useRef<(() => void) | null>(null);
  const [pressedId, setPressedId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [text, setText] = useState("");
  const { conversations, newConversation, send: sendMessage, sendToConversation, state, turns: messages } =
    useKernelSession();
  const settings = useSettings();
  const [shown, setShown] = useState(false);
  const [singleLine, setSingleLine] = useState(true);
  const [fit, setFit] = useState({
    width: dialogGlass.expandedWidth,
    height: dialogGlass.expandedHeight,
  });
  const reduced = prefersReducedMotion();
  const open = shown && messages.length > 0;
  const panel = useChatFrame(open, reduced);
  const visible = open && !panel.minimized;
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsFrame = useChatFrame(settingsOpen, reduced);
  const settingsVisible = settingsOpen && !settingsFrame.minimized;
  const [appsOpen, setAppsOpen] = useState(false);
  const [appsFocusFeatureId, setAppsFocusFeatureId] = useState<string | null>(null);
  const appsFrame = useChatFrame(appsOpen, reduced);
  const appsVisible = appsOpen && !appsFrame.minimized;
  const [toolOpen, setToolOpen] = useState(false);
  const [toolAppId, setToolAppId] = useState<string | null>(null);
  const [askWhere, setAskWhere] = useState(false);
  const [selectedConversationId, setSelectedConversationId] = useState("");
  const toolFrame = useChatFrame(toolOpen, reduced);
  const toolVisible = toolOpen && !toolFrame.minimized;
  const openSettings = () => {
    if (visible) {
      panel.toggleMinimize();
    }
    if (appsVisible) {
      appsFrame.toggleMinimize();
    }
    if (toolVisible) {
      toolFrame.toggleMinimize();
    }
    if (!settingsOpen) {
      setSettingsOpen(true);
      return;
    }
    settingsFrame.restoreIfMinimized();
  };
  const openApps = (featureId?: string) => {
    setAppsFocusFeatureId(featureId ?? null);
    if (visible) {
      panel.toggleMinimize();
    }
    if (settingsVisible) {
      settingsFrame.toggleMinimize();
    }
    if (toolVisible) {
      toolFrame.toggleMinimize();
    }
    if (!appsOpen) {
      setAppsOpen(true);
      return;
    }
    appsFrame.restoreIfMinimized();
  };
  const openTool = (id: string) => {
    setToolAppId(id);
    if (visible) {
      panel.toggleMinimize();
    }
    if (settingsVisible) {
      settingsFrame.toggleMinimize();
    }
    if (appsVisible) {
      appsFrame.toggleMinimize();
    }
    if (!toolOpen) {
      setToolOpen(true);
      return;
    }
    toolFrame.restoreIfMinimized();
  };
  const width = expanded ? fit.width : glass.width;
  const height = expanded ? fit.height : glass.height;
  const barStyle: CSSProperties = {
    position: "absolute",
    width: `min(${width}px, calc(100% - 48px))`,
    height,
    left: "50%",
    bottom: glass.bottom,
    transform: "translateX(-50%)",
    zIndex: 30,
    transition: reduced
      ? "none"
      : `width ${PRESS_DURATION}s ${PRESS_EASE}, height ${PRESS_DURATION}s ${PRESS_EASE}`,
  };

  useEffect(() => {
    if (!expanded) {
      return;
    }
    const close = (event: PointerEvent) => {
      const bar = barRef.current;
      if (bar && event.target instanceof Node && bar.contains(event.target)) {
        return;
      }
      setExpanded(false);
      inputRef.current?.blur();
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [expanded]);

  useLayoutEffect(() => {
    const area = inputRef.current;
    if (!area) {
      return;
    }
    const previousTop = area.style.paddingTop;
    const previousBottom = area.style.paddingBottom;
    const previousWidth = area.style.width;
    const previousFlex = area.style.flex;
    const previousHeight = area.style.height;
    const measureWidth = (expanded ? glass.expandedWidth : glass.width) - RAIL_WIDTH;
    area.style.flex = "none";
    area.style.width = `${measureWidth}px`;
    area.style.height = "auto";
    area.style.paddingTop = `${TEXT_PAD}px`;
    area.style.paddingBottom = `${TEXT_PAD}px`;
    const needed = area.scrollHeight;
    area.style.flex = previousFlex;
    area.style.width = previousWidth;
    area.style.height = previousHeight;
    area.style.paddingTop = previousTop;
    area.style.paddingBottom = previousBottom;
    const content = Math.max(LINE_HEIGHT, needed - TEXT_PAD * 2);
    const lines = Math.max(1, Math.round(content / LINE_HEIGHT));
    setSingleLine(lines <= 1);
    if (!expanded) {
      setFit((current) =>
        current.width === glass.expandedWidth && current.height === glass.expandedHeight
          ? current
          : { width: glass.expandedWidth, height: glass.expandedHeight },
      );
      return;
    }
    let nextHeight = glass.expandedHeight;
    let nextWidth = glass.expandedWidth;
    if (lines > 2) {
      const wantedHeight = Math.min(
        glass.maxHeight,
        Math.max(glass.expandedHeight, content + TEXT_PAD * 2),
      );
      const span = glass.maxHeight - glass.expandedHeight;
      const ratio = span <= 0 ? 1 : (wantedHeight - glass.expandedHeight) / span;
      nextHeight = wantedHeight;
      nextWidth = Math.round(glass.expandedWidth + ratio * (glass.maxWidth - glass.expandedWidth));
    }
    setFit((current) =>
      current.width === nextWidth && current.height === nextHeight
        ? current
        : { width: nextWidth, height: nextHeight },
    );
  }, [text, expanded, glass]);

  const bindRail = (node: HTMLDivElement | null) => {
    railWheelRef.current?.();
    railWheelRef.current = null;
    railRef.current = node;
    if (!node) {
      return;
    }
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();
      const page = node.clientHeight;
      if (page <= 0) {
        return;
      }
      const direction = event.deltaY > 0 ? 1 : -1;
      const index = Math.max(
        0,
        Math.min(railApps.length - 1, Math.round(node.scrollTop / page) + direction),
      );
      node.scrollTo({
        top: index * page,
        behavior: prefersReducedMotion() ? "auto" : "smooth",
      });
    };
    node.addEventListener("wheel", onWheel, { passive: false });
    railWheelRef.current = () => node.removeEventListener("wheel", onWheel);
  };

  const showConversation = () => {
    if (settingsVisible) {
      settingsFrame.toggleMinimize();
    }
    if (appsVisible) {
      appsFrame.toggleMinimize();
    }
    if (toolVisible) {
      toolFrame.toggleMinimize();
    }
    setShown(true);
    setExpanded(false);
    panel.restoreIfMinimized();
  };

  const modelChanges = () =>
    settings.card.startsWith("model.") ? [{ topic: "model", value: settings.card }] : undefined;
  const linopeId = loopAppId(loops);
  const loopCapability = toolAppId ? loops[toolAppId] : undefined;
  const loopConversations = loopCapability
    ? conversations.filter((item) => item.capability === loopCapability)
    : [];
  const selectedConversation =
    loopConversations.find((item) => item.id === selectedConversationId) ?? loopConversations[0] ?? null;
  const activePids = new Set(state.activeTurns.values());
  const conversationTabs = loopConversations.map((item) => ({
    id: item.id,
    pid: item.pid,
    queued: item.queue.length,
    running:
      item.awaiting ||
      Boolean(item.pid && activePids.has(item.pid)) ||
      state.processes.some((process) => process.id === item.pid && process.activity === "busy"),
  }));
  const loopProcess = selectedConversation?.pid
    ? state.processes.find((item) => item.id === selectedConversation.pid) ?? null
    : null;
  const loopTasks = loopProcess ? state.tasks.filter((task) => task.pid === loopProcess.id) : [];
  const loopMessages = hostedMessages(state, loopCapability, selectedConversation?.pid);

  const deliverToLoop = (value: string, capability: string, appId: string) => {
    if (toolAppId !== appId || !toolVisible) {
      openTool(appId);
    }
    const current =
      capability === loopCapability
        ? selectedConversation
        : conversations.find((item) => item.capability === capability) ?? null;
    const sentId = current
      ? sendToConversation(current.id, value)
        ? current.id
        : ""
      : newConversation(capability, modelChanges(), value);
    if (!sentId) return;
    setSelectedConversationId(sentId);
    setText("");
    setAskWhere(false);
    inputRef.current?.blur();
  };

  const deliverToChat = (value: string) => {
    const sent = sendMessage(value);
    if (!sent) return;
    setText("");
    setAskWhere(false);
    showConversation();
    inputRef.current?.blur();
  };

  const send = () => {
    const value = text.trim();
    if (!value) return;
    const route = routeDraft(toolAppId, loops);
    if (route.kind === "loop") {
      deliverToLoop(value, route.capability, route.appId);
      return;
    }
    setAskWhere(true);
  };

  useEffect(() => () => railWheelRef.current?.(), []);

  useLayoutEffect(() => {
    const rail = railRef.current;
    if (!rail || rail.clientHeight <= 0) {
      return;
    }
    const page = rail.clientHeight;
    const index = Math.round(rail.scrollTop / page);
    rail.scrollTop = index * page;
  }, [height]);

  return (
    <div className="absolute inset-0">
      <Glass
        blur={glass.blur}
        chroma={glass.chroma}
        className="absolute inset-0"
        depth={glass.depth}
        domeDepth={glass.domeDepth}
        edgeHighlight={glass.edgeHighlight}
        glow={glass.glow}
        lens={
          <>
            <div
              data-glass-lens
              style={{
                ...barStyle,
                borderRadius: glass.radius,
                boxShadow: lensShadow,
              }}
            />
            <ChatLensSlot frame={panel.frame} open={visible} />
            <SettingsLensSlot frame={settingsFrame.frame} open={settingsVisible} />
            <AppsLensSlot frame={appsFrame.frame} open={appsVisible} />
            <ToolLensSlot frame={toolFrame.frame} open={toolVisible} />
          </>
        }
        scaleX={glass.scale}
        scaleY={glass.scale}
        tint={glass.tint}
        tintBlur={glass.tintBlur}
        tintColor={glass.tintColor}
      >
        {children}
      </Glass>
      <ChatIsland
        active={panel.minimized}
        detail={
          messages.length === 0
            ? "没有消息"
            : state.status === "running"
              ? "处理中"
              : "有消息"
        }
        onRestore={() => {
          if (settingsVisible) {
            settingsFrame.toggleMinimize();
          }
          if (appsVisible) {
            appsFrame.toggleMinimize();
          }
          if (toolVisible) {
            toolFrame.toggleMinimize();
          }
          panel.toggleMinimize();
        }}
      />
      <AppsIsland
        active={appsFrame.minimized}
        onRestore={() => {
          if (visible) {
            panel.toggleMinimize();
          }
          if (settingsVisible) {
            settingsFrame.toggleMinimize();
          }
          if (toolVisible) {
            toolFrame.toggleMinimize();
          }
          appsFrame.toggleMinimize();
        }}
      />
      <SettingsIsland
        active={settingsFrame.minimized}
        onRestore={() => {
          if (visible) {
            panel.toggleMinimize();
          }
          if (appsVisible) {
            appsFrame.toggleMinimize();
          }
          if (toolVisible) {
            toolFrame.toggleMinimize();
          }
          settingsFrame.toggleMinimize();
        }}
      />
      <ToolIsland
        active={toolFrame.minimized}
        appId={toolAppId}
        onRestore={() => {
          if (visible) {
            panel.toggleMinimize();
          }
          if (settingsVisible) {
            settingsFrame.toggleMinimize();
          }
          if (appsVisible) {
            appsFrame.toggleMinimize();
          }
          toolFrame.toggleMinimize();
        }}
      />
      <ChatTranscriptSlot
        frame={panel.frame}
        fullscreen={panel.fullscreen}
        messages={messages}
        minimized={false}
        running={state.status === "running"}
        onClose={() => panel.close(() => setShown(false))}
        onFullscreen={panel.toggleFullscreen}
        onMinimize={panel.toggleMinimize}
        onResizeStart={panel.startResize}
        open={visible}
        reduced={reduced}
      />
      <SettingsBodySlot
        frame={settingsFrame.frame}
        fullscreen={settingsFrame.fullscreen}
        onClose={() => settingsFrame.close(() => setSettingsOpen(false))}
        onFullscreen={settingsFrame.toggleFullscreen}
        onMinimize={settingsFrame.toggleMinimize}
        onResizeStart={settingsFrame.startResize}
        open={settingsVisible}
        processes={state.processes}
        tasks={state.tasks}
      />
      <AppsBodySlot
        frame={appsFrame.frame}
        fullscreen={appsFrame.fullscreen}
        focusFeatureId={appsFocusFeatureId}
        onClose={() =>
          appsFrame.close(() => {
            setAppsOpen(false);
            setAppsFocusFeatureId(null);
          })
        }
        onFocusConsumed={() => setAppsFocusFeatureId(null)}
        onFullscreen={appsFrame.toggleFullscreen}
        onMinimize={appsFrame.toggleMinimize}
        onResizeStart={appsFrame.startResize}
        open={appsVisible}
      />
      {toolAppId ? (
        <ToolBodySlot
          appId={toolAppId}
          capability={loopCapability}
          conversations={conversationTabs}
          frame={toolFrame.frame}
          fullscreen={toolFrame.fullscreen}
          messages={loopMessages}
          onClose={() =>
            toolFrame.close(() => {
              setToolOpen(false);
              setToolAppId(null);
            })
          }
          onCreateConversation={() => {
            if (!loopCapability) return;
            const id = newConversation(loopCapability, modelChanges());
            if (id) setSelectedConversationId(id);
          }}
          onFullscreen={toolFrame.toggleFullscreen}
          onMinimize={toolFrame.toggleMinimize}
          onResizeStart={toolFrame.startResize}
          onSelectConversation={setSelectedConversationId}
          open={toolVisible}
          process={loopProcess}
          selectedId={selectedConversation?.id ?? ""}
          tasks={loopTasks}
        />
      ) : null}
      <EdgeSidebar onOpenApp={openTool} onOpenStore={() => openApps()} />
      {askWhere && text.trim() ? (
        <div
          className="pointer-events-auto absolute flex items-center gap-2"
          style={{
            ...dialogSurface,
            left: "50%",
            bottom: glass.bottom + height + 12,
            transform: "translateX(-50%)",
            zIndex: 40,
            borderRadius: 16,
            padding: "10px 12px",
            color: "#1c1c1e",
          }}
        >
          <span style={{ fontSize: 14, lineHeight: "20px" }}>这句话要交给哪里？</span>
          <button
            className="cursor-pointer border-0"
            onClick={() => deliverToChat(text.trim())}
            style={{ borderRadius: 999, background: "rgba(255,255,255,0.82)", padding: "6px 12px" }}
            type="button"
          >
            对话
          </button>
          {linopeId ? (
            <button
              className="cursor-pointer border-0"
              onClick={() => deliverToLoop(text.trim(), loops[linopeId], linopeId)}
              style={{ borderRadius: 999, background: "rgba(255,255,255,0.82)", padding: "6px 12px" }}
              type="button"
            >
              linope
            </button>
          ) : null}
        </div>
      ) : null}
      <div
        className="pointer-events-none absolute flex items-center justify-end"
        ref={barRef}
        style={barStyle}
      >
        <textarea
          aria-label="输入"
          className="pointer-events-auto h-full min-w-0 flex-1 resize-none border-0 bg-transparent px-3 text-[15px] leading-5 text-[#1c1c1e]"
          onChange={(event) => setText(event.target.value)}
          onFocus={() => setExpanded(true)}
          onKeyDown={(event) => {
            if (
              event.key !== "Enter" ||
              event.shiftKey ||
              event.nativeEvent.isComposing ||
              event.keyCode === 229
            ) {
              return;
            }
            event.preventDefault();
            send();
          }}
          onPointerDown={() => setExpanded(true)}
          onWheel={(event) => event.stopPropagation()}
          ref={inputRef}
          rows={1}
          style={{
            outline: "none",
            boxShadow: "none",
            caretColor: "#1c1c1e",
            lineHeight: `${LINE_HEIGHT}px`,
            paddingTop: singleLine ? Math.max(0, (height - LINE_HEIGHT) / 2) : TEXT_PAD,
            paddingBottom: singleLine ? Math.max(0, (height - LINE_HEIGHT) / 2) : TEXT_PAD,
            overflowX: "hidden",
            overflowY: singleLine ? "hidden" : "auto",
            overflowWrap: "anywhere",
            whiteSpace: "pre-wrap",
            scrollbarWidth: "none",
          }}
          value={text}
        />
        <div
          aria-hidden="true"
          style={{
            width: 1,
            height: 24,
            background: "rgba(30, 30, 36, 0.45)",
          }}
        />
        <div
          aria-label="应用"
          className="pointer-events-auto h-full w-11 shrink-0 overflow-y-auto"
          ref={bindRail}
          style={{ scrollbarWidth: "none", scrollSnapType: "y mandatory" }}
        >
          {railApps.map((app) => (
            <div
              className="grid h-full shrink-0 place-items-center"
              key={app.id}
              style={{ scrollSnapAlign: "start" }}
            >
              <button
                aria-label={app.label}
                className="grid size-9 cursor-pointer place-items-center border-0 bg-transparent p-0"
                onPointerCancel={() => setPressedId(null)}
                onPointerDown={(event) => {
                  setPressedId(app.id);
                  try {
                    event.currentTarget.setPointerCapture(event.pointerId);
                  } catch {
                    // 指针已经松开时，捕获会失败，回弹仍由 pointerup 负责。
                  }
                }}
                onPointerUp={() => {
                  setPressedId(null);
                  if (app.id === "settings") {
                    openSettings();
                  }
                  if (app.id === "all") {
                    openApps();
                  }
                }}
                style={{
                  outline: "none",
                  boxShadow: "none",
                  transform: pressedId === app.id && !reduced ? "scale(0.86)" : "scale(1)",
                  transition: reduced
                    ? "none"
                    : `transform ${pressedId === app.id ? PRESS_DURATION : RELEASE_DURATION}s ${PRESS_EASE}`,
                }}
                type="button"
              >
                <img alt="" draggable={false} height={22} src={app.icon} width={22} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export { Dialog };
