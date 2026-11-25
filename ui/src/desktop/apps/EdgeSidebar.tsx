import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { prefersReducedMotion } from "@/components/ui/glass-motion";
import { APPS } from "@/desktop/apps/catalog";
import { markAppUsed, useInstalledApps } from "@/desktop/apps/installed";
import { dialogSurface } from "@/desktop/dialog/glass";
import codeIcon from "@/desktop/apps/icons/代码.svg";
import contextIcon from "@/desktop/apps/icons/上下文.png";
import fileIcon from "@/desktop/apps/icons/文件.svg";
import loopLogo from "@/desktop/apps/icons/2f4014a4d031fae593e3b39842950b7d.jpg";
import sandboxLogo from "@/desktop/apps/icons/5ea23a3a592737f004949841de4d3bee.jpg";
import searchIcon from "@/desktop/apps/icons/搜索.svg";
import terminalIcon from "@/desktop/apps/icons/终端.svg";
import mcpHubIcon from "@/desktop/apps/icons/image.png";

type EdgeSidebarProps = {
  onOpenApp: (id: string) => void;
  onOpenStore: () => void;
};

type SidebarFeature = {
  category: string;
  icon?: string;
  id: string;
  name: string;
};

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

const features: SidebarFeature[] = APPS.flatMap((app) =>
  app.features.map((feature) => ({
    category: app.name,
    icon: featureIcons[feature.name],
    id: `${app.id}:${feature.name}`,
    name: feature.name,
  })),
);

function EdgeSidebar({ onOpenApp, onOpenStore }: EdgeSidebarProps) {
  const [expanded, setExpanded] = useState(false);
  const rootRef = useRef<HTMLElement>(null);
  const installedApps = useInstalledApps();
  const previousCount = useRef(installedApps.length);
  const reduced = prefersReducedMotion();

  useEffect(() => {
    if (installedApps.length > previousCount.current) {
      setExpanded(true);
    }
    previousCount.current = installedApps.length;
  }, [installedApps.length]);

  useEffect(() => {
    if (!expanded) return;
    const close = (event: PointerEvent) => {
      const root = rootRef.current;
      if (root && event.target instanceof Node && root.contains(event.target)) return;
      setExpanded(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [expanded]);

  const openApp = (id: string) => {
    markAppUsed(id);
    setExpanded(false);
    onOpenApp(id);
  };
  const visibleApps = installedApps.flatMap((installed) => {
    const feature = features.find((item) => item.id === installed.id);
    return feature ? [{ feature, installed }] : [];
  });

  return (
    <motion.aside
      animate={{ width: expanded ? 248 : 18 }}
      aria-label="应用侧边栏"
      ref={rootRef}
      style={{
        ...dialogSurface,
        border: "1px solid rgba(255,255,255,0.68)",
        borderLeft: 0,
        borderRadius: "0 22px 22px 0",
        boxShadow: "0 12px 34px rgba(12, 16, 30, 0.22)",
        color: "#1c1c1e",
        maxHeight: "min(72vh, 620px)",
        minHeight: 112,
        overflow: "hidden",
        position: "absolute",
        top: "50%",
        y: "-50%",
        zIndex: 20,
      }}
      transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 360, damping: 30 }}
    >
      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            animate={{ opacity: 1 }}
            className="flex h-full min-h-0 w-[248px] flex-col"
            exit={{ opacity: 0 }}
            initial={{ opacity: 0 }}
            transition={reduced ? { duration: 0 } : { duration: 0.14 }}
          >
            <div className="flex items-center gap-2 px-4 pb-2 pt-3">
              <div className="min-w-0 flex-1">
                <div style={{ fontSize: 15, fontWeight: 700, lineHeight: "20px" }}>常用应用</div>
                <div style={{ color: "rgba(28,28,30,0.58)", fontSize: 12, lineHeight: "17px" }}>
                  {visibleApps.length} 个已下载
                </div>
              </div>
              <button
                aria-label="收起应用侧边栏"
                className="grid size-8 cursor-pointer place-items-center rounded-full border-0 bg-white/55 text-lg"
                onClick={() => setExpanded(false)}
                type="button"
              >
                ‹
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2" style={{ scrollbarWidth: "thin" }}>
              {visibleApps.length === 0 ? (
                <div
                  className="mx-1 mt-2 rounded-2xl bg-white/35 px-3 py-4 text-center"
                  style={{ color: "rgba(28,28,30,0.62)", fontSize: 13, lineHeight: "19px" }}
                >
                  还没有下载的应用
                </div>
              ) : (
                visibleApps.map(({ feature, installed }) => {
                  return (
                    <button
                      aria-label={`打开 ${feature.name}`}
                      className="flex w-full cursor-pointer items-center gap-2 rounded-2xl border-0 bg-transparent px-2 py-2 text-left transition-colors hover:bg-white/48"
                      key={feature.id}
                      onClick={() => openApp(feature.id)}
                      type="button"
                    >
                      <FeatureIcon feature={feature} />
                      <span className="min-w-0 flex-1">
                        <span
                          className="block overflow-hidden text-ellipsis whitespace-nowrap"
                          style={{ fontSize: 14, fontWeight: 650, lineHeight: "19px" }}
                        >
                          {feature.name}
                        </span>
                        <span
                          className="block overflow-hidden text-ellipsis whitespace-nowrap"
                          style={{ color: "rgba(28,28,30,0.58)", fontSize: 12, lineHeight: "16px" }}
                        >
                          {feature.category}
                        </span>
                      </span>
                      <span
                        aria-label={`使用 ${installed.useCount} 次`}
                        style={{ color: "rgba(28,28,30,0.48)", fontSize: 11, lineHeight: "16px" }}
                      >
                        {installed.useCount}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
            <button
              className="mx-3 mb-3 mt-1 flex cursor-pointer items-center justify-center rounded-xl border border-white/65 bg-white/50 px-3 py-2 text-sm font-semibold"
              onClick={() => {
                setExpanded(false);
                onOpenStore();
              }}
              type="button"
            >
              打开应用中心
            </button>
          </motion.div>
        ) : (
          <button
            aria-expanded={false}
            aria-label="展开应用侧边栏"
            className="flex h-full min-h-[112px] w-[18px] cursor-pointer items-center justify-center border-0 bg-transparent p-0"
            onClick={() => setExpanded(true)}
            type="button"
          >
            <span
              aria-hidden="true"
              style={{
                color: "rgba(28,28,30,0.7)",
                fontSize: 19,
                fontWeight: 600,
                transform: "translateX(-1px)",
              }}
            >
              ›
            </span>
          </button>
        )}
      </AnimatePresence>
    </motion.aside>
  );
}

function FeatureIcon({ feature }: { feature: SidebarFeature }) {
  return (
    <span
      aria-hidden="true"
      className="grid size-10 shrink-0 place-items-center overflow-hidden rounded-xl bg-white/70"
      style={{ fontSize: 16, fontWeight: 700 }}
    >
      {feature.icon ? (
        <img alt="" draggable={false} height={32} src={feature.icon} width={32} />
      ) : (
        feature.name.slice(0, 1)
      )}
    </span>
  );
}

export { EdgeSidebar };
