import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";
import { AnimatePresence, motion, type MotionValue } from "motion/react";
import { prefersReducedMotion } from "@/components/ui/glass-motion";
import { useDeferredBody } from "@/desktop/dialog/defer-body";
import { dialogGlass, dialogSurface } from "@/desktop/dialog/glass";
import { lensShadow } from "@/desktop/dialog/ChatPanel";
import { WindowControls } from "@/desktop/dialog/WindowControls";
import { useIslandActions } from "@/lib/island";
import { APPS, type AppEntry, type AppId } from "@/desktop/apps/catalog";
import { installApp, markAppUsed, useInstalledApps } from "@/desktop/apps/installed";
import codeIcon from "@/desktop/apps/icons/代码.svg";
import codePoster from "@/desktop/apps/icons/0a2a4ed8fe487be18d9a3de6df815b67.jpg";
import contextIcon from "@/desktop/apps/icons/上下文.png";
import contextPoster from "@/desktop/apps/icons/智能上下文压缩工具.png";
import downloadIcon from "@/desktop/apps/icons/下载.svg";
import mcpHubIcon from "@/desktop/apps/icons/image.png";
import fileIcon from "@/desktop/apps/icons/文件.svg";
import filePoster from "@/desktop/apps/icons/文件读写工具：快速、安全、高效.png";
import loopLogo from "@/desktop/apps/icons/2f4014a4d031fae593e3b39842950b7d.jpg";
import loopPoster from "@/desktop/apps/icons/智能代理循环：持续思考与进化.png";
import sandboxIcon from "@/desktop/apps/icons/沙箱.svg";
import sandboxLogo from "@/desktop/apps/icons/5ea23a3a592737f004949841de4d3bee.jpg";
import sandboxPoster from "@/desktop/apps/icons/7bafeea92765a97475715e2f0cfff50e.jpg";
import searchIcon from "@/desktop/apps/icons/搜索.svg";
import terminalIcon from "@/desktop/apps/icons/终端.svg";

const featureIcons: Record<string, string> = {
  文件: fileIcon,
  终端: terminalIcon,
  网页搜索: searchIcon,
  运行代码: codeIcon,
  linope: loopLogo,
  沙盒工具: sandboxLogo,
  上下文压缩工具: contextIcon,
  MCPHub: mcpHubIcon,
};

const familyIcons: Partial<Record<AppId, string>> = {
  sandbox: sandboxIcon,
  context: contextIcon,
};

const featuredPosters: Partial<Record<AppId, string>> = {
  file: filePoster,
  code: codePoster,
  sandbox: sandboxPoster,
  context: contextPoster,
  loop: loopPoster,
};

type AppFrame = {
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
const quiet = "rgba(28,28,30,0.62)";
const fill = "rgba(255,255,255,0.55)";
const fillSoft = "rgba(255,255,255,0.34)";
const cardFrame = {
  borderRadius: 14,
  background: "rgba(255,255,255,0.62)",
  border: "1px solid rgba(255,255,255,0.88)",
  boxShadow: "inset 0 0 0 1px rgba(28,28,30,0.1), 0 1px 2px rgba(28,28,30,0.08)",
} as const;
const panelFrame = {
  borderRadius: 16,
  background: "rgba(255,255,255,0.3)",
  border: "1px solid rgba(255,255,255,0.62)",
  padding: 10,
} as const;

const islandLine = {
  fontSize: 15,
  fontWeight: 600,
  lineHeight: "20px",
} as const;

const islandExpandedLine = {
  ...islandLine,
  marginLeft: 12,
};

const featuredBannerFrame = {
  width: "100%",
  aspectRatio: "16 / 9",
  minHeight: 164,
  boxSizing: "border-box",
} as const;

function frameStyle(frame: AppFrame) {
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

function lensFrameStyle(frame: AppFrame) {
  return {
    position: "absolute" as const,
    left: frame.left,
    top: frame.lensTop,
    width: frame.width,
    height: frame.lensHeight,
    borderRadius: dialogGlass.radius,
  };
}

function AppsLensSlot({ frame, open }: { frame: AppFrame; open: boolean }) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div data-glass-lens key="apps-lens" style={{ ...lensFrameStyle(frame), boxShadow: lensShadow }} />
      ) : null}
    </AnimatePresence>
  );
}

function AppsBodySlot({
  frame,
  fullscreen,
  focusFeatureId,
  onClose,
  onFocusConsumed,
  onFullscreen,
  onMinimize,
  onResizeStart,
  open,
}: {
  frame: AppFrame;
  fullscreen: boolean;
  focusFeatureId: string | null;
  onClose: () => void;
  onFocusConsumed: () => void;
  onFullscreen: () => void;
  onMinimize: () => void;
  onResizeStart: ResizeStart;
  open: boolean;
}) {
  const bodyReady = useDeferredBody(open);
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          aria-label="应用"
          className="pointer-events-auto absolute overflow-hidden"
          key="apps-window"
          role="dialog"
          style={{ ...frameStyle(frame), ...dialogSurface }}
        >
          <motion.div
            className="flex h-full w-full flex-col"
            onWheel={(event) => event.stopPropagation()}
            style={{ color: ink, opacity: frame.textOpacity }}
          >
            {bodyReady ? (
              <AppsHome focusFeatureId={focusFeatureId} onFocusConsumed={onFocusConsumed} />
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

type FeatureItem = {
  id: string;
  name: string;
  detail: string;
  categoryId: AppId;
  category: string;
};

type Place = { kind: "discover" } | { kind: "category"; id: AppId } | { kind: "family"; id: AppId };

type Screen = Place | { kind: "feature"; id: string; back: Place };

const features: FeatureItem[] = APPS.flatMap((app) =>
  app.features.map((feature) => ({
    id: `${app.id}:${feature.name}`,
    name: feature.name,
    detail: feature.detail,
    categoryId: app.id,
    category: app.name,
  })),
);

const sidebarApps = [
  ...APPS.filter((app) => app.id !== "other"),
  ...APPS.filter((app) => app.id === "other"),
];

const featuredApps = APPS.filter((app) => app.featured);

function placeOf(screen: Screen): Place {
  return screen.kind === "feature" ? screen.back : screen;
}

function matchesFeature(feature: FeatureItem, query: string) {
  const text = query.trim().toLowerCase();
  if (!text) return true;
  return `${feature.name}\n${feature.detail}\n${feature.category}`.toLowerCase().includes(text);
}

function AppsHome({
  focusFeatureId,
  onFocusConsumed,
}: {
  focusFeatureId: string | null;
  onFocusConsumed: () => void;
}) {
  const [query, setQuery] = useState("");
  const [slide, setSlide] = useState(0);
  const [screen, setScreen] = useState<Screen>({ kind: "discover" });
  const scroller = useRef<HTMLDivElement>(null);
  const installedApps = useInstalledApps();
  const installedIds = new Set(installedApps.map((app) => app.id));
  const searching = query.trim().length > 0;
  const place = placeOf(screen);

  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 });
  }, [screen, searching]);

  useEffect(() => {
    if (!focusFeatureId) return;
    if (features.some((feature) => feature.id === focusFeatureId)) {
      setQuery("");
      setScreen({ kind: "feature", id: focusFeatureId, back: { kind: "discover" } });
    }
    onFocusConsumed();
  }, [focusFeatureId, onFocusConsumed]);

  const openFeature = (id: string) => {
    if (installedIds.has(id)) {
      markAppUsed(id);
    }
    setScreen({ kind: "feature", id, back: place });
  };

  return (
    <div className="flex min-h-0 flex-1 pt-11">
      <aside className="flex w-[168px] shrink-0 flex-col gap-3 px-3 pb-4">
        <label className="flex items-center gap-2" style={{ borderRadius: 10, background: fillSoft, padding: "7px 10px" }}>
          <SearchMark />
          <input
            aria-label="搜索"
            autoComplete="off"
            className="min-w-0 flex-1 border-0 bg-transparent p-0"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索"
            spellCheck={false}
            style={{ color: ink, fontSize: 14, lineHeight: "18px", outline: "none" }}
            value={query}
          />
        </label>
        <nav aria-label="分类" className="flex flex-col gap-1">
          <NavButton
            label="发现"
            onClick={() => {
              setQuery("");
              setScreen({ kind: "discover" });
            }}
            selected={!searching && (place.kind === "discover" || place.kind === "family")}
          />
          <div style={{ margin: "8px 10px 2px", fontSize: 11, fontWeight: 650, letterSpacing: "0.04em", color: quiet }}>
            分类
          </div>
          {sidebarApps.map((app) => (
            <NavButton
              key={app.id}
              label={app.name}
              onClick={() => {
                setQuery("");
                setScreen({ kind: "category", id: app.id });
              }}
              selected={!searching && place.kind === "category" && place.id === app.id}
            />
          ))}
        </nav>
      </aside>
      <div
        className="min-h-0 min-w-0 flex-1 overflow-y-auto px-4 pb-5"
        ref={scroller}
        style={{ scrollbarWidth: "thin", overscrollBehavior: "contain" }}
      >
        {screen.kind === "feature" ? (
          <FeaturePage featureId={screen.id} onBack={() => setScreen(screen.back)} />
        ) : screen.kind === "family" ? (
          <FamilyPage id={screen.id} onBack={() => setScreen({ kind: "discover" })} onOpen={openFeature} />
        ) : searching ? (
          <FeatureList
            empty="没有匹配的插件。"
            features={features.filter((feature) => matchesFeature(feature, query))}
            onOpen={openFeature}
            title="搜索"
          />
        ) : screen.kind === "category" ? (
          <FeatureList
            empty="没有匹配的插件。"
            features={features.filter((feature) => feature.categoryId === screen.id)}
            onOpen={openFeature}
            title={APPS.find((app) => app.id === screen.id)?.name ?? "分类"}
          />
        ) : (
          <Discover
            onOpenFamily={(id) => setScreen({ kind: "family", id })}
            onOpenFeature={openFeature}
            onSlide={setSlide}
            slide={slide}
          />
        )}
      </div>
    </div>
  );
}

function Discover({
  onOpenFamily,
  onOpenFeature,
  onSlide,
  slide,
}: {
  onOpenFamily: (id: AppId) => void;
  onOpenFeature: (id: string) => void;
  onSlide: (index: number) => void;
  slide: number;
}) {
  const [paused, setPaused] = useState(false);
  const reduced = prefersReducedMotion();
  const app = featuredApps[slide] ?? featuredApps[0];

  useEffect(() => {
    if (paused || reduced || featuredApps.length < 2) return;
    const timer = window.setInterval(() => {
      onSlide((slide + 1) % featuredApps.length);
    }, 4200);
    return () => window.clearInterval(timer);
  }, [onSlide, paused, reduced, slide]);

  return (
    <div>
      <div onPointerEnter={() => setPaused(true)} onPointerLeave={() => setPaused(false)}>
        <div className="relative overflow-hidden">
          <AnimatePresence initial={false} mode="wait">
            {app ? (
              <motion.div
                animate={{ opacity: 1, x: 0 }}
                exit={reduced ? undefined : { opacity: 0, x: -28 }}
                initial={reduced ? false : { opacity: 0, x: 28 }}
                key={app.id}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              >
                <FeaturedBanner app={app} onOpen={() => onOpenFamily(app.id)} />
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
        <div className="mt-3 flex justify-center gap-1.5">
          {featuredApps.map((item, index) => (
            <button
              aria-label={item.name}
              key={item.id}
              onClick={() => onSlide(index)}
              style={{
                width: index === slide ? 16 : 6,
                height: 6,
                border: 0,
                borderRadius: 999,
                padding: 0,
                cursor: "pointer",
                background: index === slide ? ink : "rgba(28,28,30,0.28)",
              }}
              type="button"
            />
          ))}
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        {APPS.map((group) => (
          <section key={group.id} style={panelFrame}>
            <h3 style={{ margin: "0 0 8px", fontSize: 15, fontWeight: 700, lineHeight: "20px" }}>{group.name}</h3>
            <div className="flex flex-col gap-2">
              {features
                .filter((feature) => feature.categoryId === group.id)
                .map((feature) => (
                  <ToolCard feature={feature} key={feature.id} onOpen={() => onOpenFeature(feature.id)} />
                ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function FeaturedBanner({ app, onOpen }: { app: AppEntry; onOpen: () => void }) {
  const openKeys = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpen();
    }
  };
  const poster = featuredPosters[app.id];
  if (poster) {
    return (
      <div
        aria-label={app.name}
        onClick={onOpen}
        onKeyDown={openKeys}
        role="link"
        style={{
          ...featuredBannerFrame,
          borderRadius: 20,
          overflow: "hidden",
          cursor: "pointer",
          lineHeight: 0,
        }}
        tabIndex={0}
      >
        <img
          alt=""
          draggable={false}
          src={poster}
          style={{ display: "block", width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
    );
  }
  return (
    <div
      onClick={onOpen}
      onKeyDown={openKeys}
      role="link"
      style={{
        ...featuredBannerFrame,
        borderRadius: 20,
        background: fill,
        padding: "16px 16px 14px",
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
      }}
      tabIndex={0}
    >
      <div style={{ fontSize: 12, fontWeight: 650, letterSpacing: "0.06em", color: quiet }}>精选</div>
      <div style={{ marginTop: 6, fontSize: 26, fontWeight: 700, lineHeight: "32px" }}>{app.name}</div>
      <div style={{ marginTop: 4, maxWidth: 420, fontSize: 14, lineHeight: "20px" }}>{app.summary}</div>
      <div className="flex items-center gap-2.5" style={{ marginTop: "auto" }}>
        <Mark label={app.name} src={familyIcons[app.id]} />
        <div className="min-w-0 flex-1">
          <div style={{ fontSize: 15, fontWeight: 650, lineHeight: "20px" }}>{app.name}</div>
          <div
            style={{
              overflow: "hidden",
              fontSize: 13,
              lineHeight: "18px",
              color: quiet,
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {app.summary}
          </div>
        </div>
        <ViewButton actionLabel="查看" name={app.name} onClick={onOpen} />
      </div>
    </div>
  );
}

function FeatureList({
  empty,
  features: rows,
  onOpen,
  title,
}: {
  empty: string;
  features: FeatureItem[];
  onOpen: (id: string) => void;
  title: string;
}) {
  return (
    <section>
      <h2 style={{ margin: "18px 0 8px", fontSize: 20, fontWeight: 700, lineHeight: "26px" }}>{title}</h2>
      {rows.length === 0 ? (
        <p style={{ margin: 0, fontSize: 15, lineHeight: "22px" }}>{empty}</p>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          {rows.map((feature) => (
            <ToolCard feature={feature} key={feature.id} onOpen={() => onOpen(feature.id)} />
          ))}
        </div>
      )}
    </section>
  );
}

function ToolCard({ feature, onOpen }: { feature: FeatureItem; onOpen: () => void }) {
  const installed = useInstalledApps().some((app) => app.id === feature.id);

  return (
    <div
      className="flex min-w-0 flex-col gap-2"
      onClick={onOpen}
      style={{
        ...cardFrame,
        padding: "10px 10px 8px",
        cursor: "pointer",
      }}
    >
      <div className="flex min-w-0 items-center gap-2">
        <Mark label={feature.name} src={featureIcons[feature.name]} />
        <div className="min-w-0">
          <div
            style={{
              overflow: "hidden",
              fontSize: 14,
              fontWeight: 650,
              lineHeight: "18px",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {feature.name}
          </div>
          <div
            style={{
              overflow: "hidden",
              marginTop: 2,
              fontSize: 12,
              lineHeight: "16px",
              color: quiet,
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {feature.category}
          </div>
        </div>
      </div>
      <div className="flex justify-end">
        <ViewButton
          installed={installed}
          name={feature.name}
          onClick={() => installApp(feature.id)}
        />
      </div>
    </div>
  );
}

function FamilyPage({ id, onBack, onOpen }: { id: AppId; onBack: () => void; onOpen: (id: string) => void }) {
  const app = APPS.find((item) => item.id === id);
  if (!app) return null;
  return (
    <div>
      <BackButton onClick={onBack} />
      <div className="mt-3 flex items-start gap-3">
        <Mark label={app.name} large src={familyIcons[app.id]} />
        <div className="min-w-0">
          <div style={{ fontSize: 26, fontWeight: 700, lineHeight: "32px" }}>{app.name}</div>
          <div style={{ marginTop: 4, fontSize: 14, lineHeight: "20px" }}>{app.summary}</div>
        </div>
      </div>
      <FeatureList
        empty="没有匹配的插件。"
        features={features.filter((feature) => feature.categoryId === app.id)}
        onOpen={onOpen}
        title="包含"
      />
    </div>
  );
}

function Description({ text }: { text: string }) {
  const paragraphs = text
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter((paragraph) => paragraph.length > 0);
  return (
    <div style={{ maxWidth: 560 }}>
      {paragraphs.map((paragraph, index) => (
        <p
          key={index}
          style={{
            margin: index === paragraphs.length - 1 ? 0 : "0 0 12px",
            fontSize: 15,
            lineHeight: "24px",
          }}
        >
          {paragraph}
        </p>
      ))}
    </div>
  );
}

function FeaturePage({ featureId, onBack }: { featureId: string; onBack: () => void }) {
  const feature = features.find((item) => item.id === featureId);
  if (!feature) return null;
  return (
    <div>
      <BackButton onClick={onBack} />
      <div className="mt-3 flex items-start gap-3">
        <Mark label={feature.name} large src={featureIcons[feature.name]} />
        <div className="min-w-0">
          <div style={{ fontSize: 26, fontWeight: 700, lineHeight: "32px" }}>{feature.name}</div>
          <div style={{ marginTop: 4, fontSize: 14, lineHeight: "20px", color: quiet }}>{feature.category}</div>
        </div>
      </div>
      <h2 style={{ margin: "18px 0 8px", fontSize: 17, fontWeight: 700, lineHeight: "22px" }}>说明</h2>
      <Description text={feature.detail} />
    </div>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      aria-label="返回"
      className="flex cursor-pointer items-center gap-1 border-0 bg-transparent p-0"
      onClick={onClick}
      style={{ color: ink, fontSize: 15, fontWeight: 600, lineHeight: "20px" }}
      type="button"
    >
      <span aria-hidden="true">‹</span>
      返回
    </button>
  );
}

function NavButton({ label, onClick, selected }: { label: string; onClick: () => void; selected: boolean }) {
  return (
    <button
      aria-pressed={selected}
      className="cursor-pointer border-0 text-left"
      onClick={onClick}
      style={{
        borderRadius: 10,
        padding: "7px 10px",
        background: selected ? fill : "transparent",
        color: ink,
        fontSize: 14,
        fontWeight: selected ? 650 : 500,
        lineHeight: "18px",
      }}
      type="button"
    >
      {label}
    </button>
  );
}

function ViewButton({
  actionLabel = "下载",
  installed = false,
  name,
  onClick,
}: {
  actionLabel?: "下载" | "查看";
  installed?: boolean;
  name: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={installed ? `${name} 已下载` : `${actionLabel} ${name}`}
      className="cursor-pointer border-0"
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      style={{
        borderRadius: 999,
        width: 32,
        height: 32,
        display: "grid",
        placeItems: "center",
        padding: 0,
        background: "rgba(255,255,255,0.86)",
      }}
      type="button"
    >
      {installed ? (
        <span aria-hidden="true" style={{ color: "#1c1c1e", fontSize: 18, fontWeight: 700, lineHeight: 1 }}>
          ✓
        </span>
      ) : (
        <img alt="" aria-hidden="true" draggable={false} height={18} src={downloadIcon} width={18} />
      )}
    </button>
  );
}

function Mark({ label, large = false, src }: { label: string; large?: boolean; src?: string }) {
  const size = large ? 64 : 40;
  const radius = large ? 16 : 12;
  return (
    <span
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        borderRadius: radius,
        display: "grid",
        placeItems: "center",
        flexShrink: 0,
        overflow: "hidden",
        background: src ? "transparent" : "rgba(255,255,255,0.78)",
        fontSize: large ? 26 : 16,
        fontWeight: 700,
      }}
    >
      {src ? (
        <img
          alt=""
          draggable={false}
          height={size}
          src={src}
          style={{
            width: size,
            height: size,
            objectFit: "cover",
            objectPosition: src === loopLogo ? "50% 100%" : undefined,
            transform:
              src === loopLogo
                ? "translateX(2px) scale(1.25)"
                : src === contextIcon
                  ? "scale(0.9)"
                  : undefined,
            transformOrigin: src === loopLogo ? "50% 100%" : undefined,
          }}
          width={size}
        />
      ) : (
        label.slice(0, 1)
      )}
    </span>
  );
}

function SearchMark() {
  return (
    <svg aria-hidden="true" fill="none" height="14" viewBox="0 0 24 24" width="14">
      <circle cx="11" cy="11" r="7" stroke={ink} strokeWidth="2" />
      <path d="M16.5 16.5L21 21" stroke={ink} strokeLinecap="round" strokeWidth="2" />
    </svg>
  );
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

function AppsIsland({ active, onRestore }: { active: boolean; onRestore: () => void }) {
  const island = useIslandActions();
  const restore = useRef(onRestore);
  restore.current = onRestore;
  const detail = "文件、代码、终端、沙箱、上下文、循环、MCP、其它";

  useEffect(() => {
    if (!active) return;
    const handle = island.start({
      id: "apps",
      label: `应用，${detail}`,
      onPress: () => {
        if (island.presentation === "expanded") {
          restore.current();
          return;
        }
        island.expand("apps");
      },
      compact: { leading: <span style={islandLine}>应用</span> },
      minimal: <span style={islandLine}>应用</span>,
      expanded: {
        leading: <span style={islandExpandedLine}>应用</span>,
        bottom: <span style={{ ...islandExpandedLine, opacity: 0.62 }}>{detail}</span>,
      },
    });
    return () => handle.end();
  }, [active, island]);

  return null;
}

export { AppsBodySlot, AppsIsland, AppsLensSlot };
