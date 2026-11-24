import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { AnimatePresence, motion, type MotionValue } from "motion/react";
import { prefersReducedMotion } from "@/components/ui/glass-motion";
import { MessageMarkdown } from "@/desktop/dialog/MessageMarkdown";
import { dialogGlass, dialogSurface } from "@/desktop/dialog/glass";
import { lensShadow } from "@/desktop/dialog/ChatPanel";
import { ModelFlow } from "@/desktop/setting/ModelFlow";
import { WindowControls } from "@/desktop/dialog/WindowControls";
import { useIslandActions } from "@/lib/island";
import {
  CARD_LIST,
  addWallpaper,
  builtinWallpapers,
  cardSpec,
  contextLimit,
  setCard,
  setCores,
  setDynamicCard,
  setLocalPath,
  setMemoryBackend,
  setPromptOverride,
  setWallpaper,
  updateDraft,
  useImageRevision,
  useSettings,
  wallpaperById,
} from "@/desktop/setting/settings";
import { useInstalledApps } from "@/desktop/apps/installed";
import {
  installedLoopLabel,
  installedLoops,
  loadedPromptText,
  promptText,
  type LoadedLoop,
} from "@/desktop/setting/loaded-loops";
import { forgetFixedPrompts, useKernelSession } from "@/desktop/link/useKernelSession";
import { occupiedTokens, type ModelPlugin, type UiProcess, type UiTask } from "@/desktop/link/state";
import { activityTaskStore } from "@/desktop/activity/task-store";

type SettingsFrame = {
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

type PageId = "model" | "context" | "memory" | "desktop";

const pages: { id: PageId; label: string }[] = [
  { id: "model", label: "模型" },
  { id: "context", label: "上下文" },
  { id: "memory", label: "记忆" },
  { id: "desktop", label: "桌面" },
];

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
const quiet = "rgba(28,28,30,0.58)";
const fill = "rgba(255,255,255,0.55)";

const islandLine = {
  fontSize: 15,
  fontWeight: 600,
  lineHeight: "20px",
} as const;

const islandExpandedLine = {
  ...islandLine,
  marginLeft: 12,
};

function frameStyle(frame: SettingsFrame) {
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

function lensFrameStyle(frame: SettingsFrame) {
  return {
    position: "absolute" as const,
    left: frame.left,
    top: frame.lensTop,
    width: frame.width,
    height: frame.lensHeight,
    borderRadius: dialogGlass.radius,
  };
}

function SettingsLensSlot({ frame, open }: { frame: SettingsFrame; open: boolean }) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          data-glass-lens
          key="settings-lens"
          style={{ ...lensFrameStyle(frame), boxShadow: lensShadow }}
        />
      ) : null}
    </AnimatePresence>
  );
}

function SettingsBodySlot({
  frame,
  fullscreen,
  onClose,
  onFullscreen,
  onMinimize,
  onResizeStart,
  lines,
  open,
  processes,
  tasks,
}: {
  frame: SettingsFrame;
  fullscreen: boolean;
  lines: string[];
  onClose: () => void;
  onFullscreen: () => void;
  onMinimize: () => void;
  onResizeStart: ResizeStart;
  open: boolean;
  processes: UiProcess[];
  tasks: UiTask[];
}) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          aria-label="设置"
          className="pointer-events-auto absolute overflow-hidden"
          key="settings-window"
          role="dialog"
          style={{ ...frameStyle(frame), ...dialogSurface }}
        >
          <motion.div
            className="flex h-full w-full"
            onWheel={(event) => event.stopPropagation()}
            style={{ color: ink, opacity: frame.textOpacity }}
          >
            <SettingsNav lines={lines} processes={processes} tasks={tasks} />
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

function SettingsNav({ lines, processes, tasks }: { lines: string[]; processes: UiProcess[]; tasks: UiTask[] }) {
  const [page, setPage] = useState<PageId>("model");
  useImageRevision();

  return (
    <>
      <nav aria-label="设置分页" className="flex w-[148px] shrink-0 flex-col gap-1 px-3 pb-4 pt-4">
        {pages.map((item) => {
          const selected = page === item.id;
          return (
            <button
              aria-current={selected ? "page" : undefined}
              className="cursor-pointer border-0 text-left"
              key={item.id}
              onClick={() => setPage(item.id)}
              style={{
                height: 36,
                borderRadius: 12,
                padding: "0 12px",
                background: selected ? fill : "transparent",
                color: ink,
                fontSize: 15,
                lineHeight: "20px",
              }}
              type="button"
            >
              {item.label}
            </button>
          );
        })}
      </nav>
      <div
        className="min-h-0 min-w-0 flex-1 overflow-y-auto px-4 pb-5 pt-12"
        style={{ scrollbarWidth: "thin", overscrollBehavior: "contain" }}
      >
        {page === "model" ? <ModelPage /> : null}
        {page === "context" ? <ContextPage lines={lines} processes={processes} tasks={tasks} /> : null}
        {page === "memory" ? <MemoryPage /> : null}
        {page === "desktop" ? <DesktopPage /> : null}
      </div>
    </>
  );
}

type ModelSection = "cores" | "card" | "link" | "generate" | "thinking" | "parameters";

const reasoningLabel = {
  "": "默认",
  low: "低",
  medium: "中",
  high: "高",
} as const;

function ModelPage() {
  const settings = useSettings();
  const session = useKernelSession();
  const [section, setSection] = useState<ModelSection | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const draft = settings.drafts[settings.card];
  const spec = cardSpec(settings.card);
  const plugin = session.modelCatalog.find((item) => item.capability === settings.card);
  const supportsOpenAi = plugin ? plugin.provider === "openai" : spec.openai;
  const modelName = draft.model.trim() || "未命名";
  const [configTask, setConfigTask] = useState<{
    taskId: string;
    configRequestId: string;
    secretRequestId?: string;
  } | null>(null);

  useEffect(() => {
    session.actions.loadModelCatalog();
  }, [session.actions.loadModelCatalog]);

  useEffect(() => {
    if (!session.modelCatalog.length || plugin) return;
    const first = session.modelCatalog.find((item) => item.ready) ?? session.modelCatalog[0];
    if (first) {
      setDynamicCard(first.capability, {
        baseUrl: first.base_url,
        model: first.model,
      });
    }
  }, [plugin, session.modelCatalog]);

  const rows: Array<{ id: ModelSection; title: string; detail: string; value: string }> = [
    {
      id: "cores",
      title: "模型核",
      detail: "接入模型后查看完整流程",
      value: `${settings.cores} 个核`,
    },
    {
      id: "card",
      title: "卡片",
      detail: "选择接口插件",
      value: plugin ? `${plugin.provider} · ${plugin.card_id}` : spec.label,
    },
    { id: "link", title: "连接", detail: "模型名、接口地址和密钥", value: modelName },
    { id: "generate", title: "生成", detail: "流式、温度、top_p 和单次长度", value: `流式${switchText(draft.stream)}` },
  ];
  if (supportsOpenAi) {
    rows.push({
      id: "thinking",
      title: "思考",
      detail: "思考开关、力度和并行工具",
      value: reasoningLabel[draft.reasoning],
    });
  }
  const customParameters = plugin?.changes.filter(
    (change) =>
      ![
        "model",
        "provider",
        "base_url",
        "max_tokens",
        "temperature",
        "top_p",
        "thinking_enable",
        "reasoning_effort",
        "parallel_tool_calls",
      ].includes(change),
  ) ?? [];
  if (customParameters.length) {
    rows.push({
      id: "parameters",
      title: "插件参数",
      detail: "插件声明的其他可变参数",
      value: `${customParameters.length} 项`,
    });
  }

  useEffect(() => {
    rootRef.current?.parentElement?.scrollTo({ top: 0 });
  }, [section]);

  useEffect(() => {
    if (!configTask) return;
    const configState = session.state.actionStates.get(configTask.configRequestId);
    const secretState = configTask.secretRequestId
      ? session.state.actionStates.get(configTask.secretRequestId)
      : undefined;
    if (configState?.status === "failed" || secretState?.status === "failed") {
      activityTaskStore.fail(
        configTask.taskId,
        configState?.status === "failed"
          ? configState.error
          : secretState?.status === "failed"
            ? secretState.error
            : "模型配置失败",
      );
      setConfigTask(null);
    } else if (
      configState?.status === "completed" &&
      (!configTask.secretRequestId || secretState?.status === "completed")
    ) {
      activityTaskStore.finish(configTask.taskId, "模型配置已完成");
      setConfigTask(null);
    }
  }, [configTask, session.state.actionStates]);

  return (
    <div className="flex flex-col gap-3" ref={rootRef}>
      {section === null ? <SettingList onOpen={setSection} rows={rows} /> : null}
      {section === "cores" ? (
        <CoresDetail
          cores={settings.cores}
          onBack={() => setSection(null)}
          ready={Boolean(plugin?.ready)}
        />
      ) : null}
      {section === "card" ? (
        <CardDetail
          card={settings.card}
          onBack={() => setSection(null)}
          plugins={session.modelCatalog}
        />
      ) : null}
      {section === "link" ? <LinkDetail onBack={() => setSection(null)} /> : null}
      {section === "generate" ? <GenerateDetail onBack={() => setSection(null)} /> : null}
      {section === "thinking" && supportsOpenAi ? <ThinkingDetail onBack={() => setSection(null)} /> : null}
      {section === "parameters" && plugin ? (
        <ParametersDetail
          names={customParameters}
          onBack={() => setSection(null)}
          values={draft.parameters}
        />
      ) : null}
      {section === null ? (
        <button
          className="cursor-pointer border-0"
          onClick={() => {
            const result = applyModelConfiguration(settings, plugin, session);
            if (result) setConfigTask(result);
          }}
          style={{
            borderRadius: 12,
            padding: "10px 12px",
            background: "rgba(255,255,255,0.78)",
            boxShadow: "inset 0 0 0 1.5px rgba(28,28,30,0.85)",
            color: ink,
            fontSize: 15,
            lineHeight: "20px",
          }}
          type="button"
        >
          应用模型配置
        </button>
      ) : null}
    </div>
  );
}

function applyModelConfiguration(
  settings: ReturnType<typeof useSettings>,
  plugin: ModelPlugin | undefined,
  session: ReturnType<typeof useKernelSession>,
): { taskId: string; configRequestId: string; secretRequestId?: string } | null {
  if (!plugin || !plugin.ready) return null;
  const draft = settings.drafts[settings.card];
  if (!draft) return null;

  const taskId = `model-configure-${Date.now()}`;
  activityTaskStore.start({
    detail: "准备模型环境",
    group: "background-tasks",
    id: taskId,
    label: "模型配置",
    priority: 5,
    status: "pending",
  });

  let secretRequestId: string | undefined;
  if (draft.apiKey.trim()) {
    const requestId = session.actions.saveSecret({
      key: plugin.api_key_env,
      value: draft.apiKey,
    });
    if (requestId) secretRequestId = requestId;
  }

  const changes: Array<{ topic: string; value: string }> = [];
  const add = (topic: string, value: string | null | undefined) => {
    if (value !== null && value !== undefined && value !== "" && plugin.changes.includes(topic)) {
      changes.push({ topic, value });
    }
  };
  add("model", draft.model.trim());
  add("base_url", draft.baseUrl.trim());
  add("stream", draft.stream === null ? null : String(draft.stream));
  add("max_tokens", draft.maxTokens.trim());
  add("temperature", draft.temperature === null ? null : String(draft.temperature));
  add("top_p", draft.topP === null ? null : String(draft.topP));
  add("thinking_enable", draft.thinking === null ? null : String(draft.thinking));
  add("reasoning_effort", draft.reasoning || null);
  add("parallel_tool_calls", draft.parallelTools === null ? null : String(draft.parallelTools));
  for (const [topic, value] of Object.entries(draft.parameters)) {
    add(topic, value);
  }

  const configRequestId = session.actions.configureModel({
    capability: plugin.capability,
    changes,
    cores: settings.cores,
  });
  if (!configRequestId) {
    activityTaskStore.fail(taskId, "无法连接到后端");
    return null;
  }
  activityTaskStore.update(taskId, {
    detail: secretRequestId ? "正在准备模型环境" : "正在安装模型卡片",
    requestId: configRequestId,
    status: "running",
  });
  return { configRequestId, secretRequestId, taskId };
}

function ParametersDetail({
  names,
  onBack,
  values,
}: {
  names: string[];
  onBack: () => void;
  values: Record<string, string>;
}) {
  const settings = useSettings();
  return (
    <div className="flex flex-col gap-3">
      <DetailBack onBack={onBack} title="插件参数" />
      {names.map((name) => (
        <Field key={name} label={name}>
          <TextInput
            ariaLabel={name}
            onChange={(value) => {
              const current = settings.drafts[settings.card];
              updateDraft({
                parameters: { ...(current?.parameters ?? {}), [name]: value },
              });
            }}
            placeholder="留空表示不设置"
            value={values[name] ?? ""}
          />
        </Field>
      ))}
    </div>
  );
}

function CoresDetail({
  cores,
  onBack,
  ready,
}: {
  cores: number;
  onBack: () => void;
  ready: boolean;
}) {
  const [taskName, setTaskName] = useState("");
  const focus = taskName.trim();
  return (
    <div className="flex flex-col gap-4">
      <DetailBack onBack={onBack} title="模型核" />
      <div className="flex items-center gap-3" style={{ ...rowStyle, width: "fit-content" }}>
        <StepButton disabled={cores <= 1} label="减少模型核" onClick={() => setCores(cores - 1)}>
          −
        </StepButton>
        <span style={{ minWidth: 24, textAlign: "center", fontSize: 15 }}>{cores}</span>
        <StepButton label="增加模型核" onClick={() => setCores(cores + 1)}>
          +
        </StepButton>
        <input
          aria-label="任务名"
          autoComplete="off"
          onChange={(event) => setTaskName(event.target.value)}
          placeholder="taskA"
          spellCheck={false}
          style={{
            width: 112,
            height: 32,
            border: 0,
            borderRadius: 999,
            outline: "none",
            background: "rgba(255,255,255,0.8)",
            color: ink,
            fontSize: 14,
            padding: "0 12px",
          }}
          value={taskName}
        />
      </div>
      {ready ? <ModelFlow cores={cores} focus={focus} /> : <p style={{ margin: 0, fontSize: 15, lineHeight: "22px" }}>接入模型后查看完整流程。</p>}
    </div>
  );
}

function CardDetail({
  card,
  onBack,
  plugins,
}: {
  card: string;
  onBack: () => void;
  plugins: ModelPlugin[];
}) {
  return (
    <div className="flex flex-col gap-3">
      <DetailBack onBack={onBack} title="卡片" />
      <div className="grid grid-cols-2 gap-2">
        {plugins.length
          ? plugins.map((item) => (
              <Choice
                key={item.capability}
                label={`${item.provider} · ${item.card_id}${item.ready ? "" : "（不可用）"}`}
                onClick={() =>
                  item.ready
                    ? setDynamicCard(item.capability, {
                        baseUrl: item.base_url,
                        model: item.model,
                      })
                    : undefined
                }
                selected={card === item.capability}
              />
            ))
          : CARD_LIST.map((item) => (
              <Choice
                key={item.id}
                label={item.label}
                onClick={() => setCard(item.id)}
                selected={card === item.id}
              />
            ))}
      </div>
    </div>
  );
}

function LinkDetail({ onBack }: { onBack: () => void }) {
  const settings = useSettings();
  const draft = settings.drafts[settings.card];

  return (
    <div className="flex flex-col gap-3">
      <DetailBack onBack={onBack} title="连接" />
      <Field label="模型名">
        <TextInput
          ariaLabel="模型名"
          onChange={(model) => updateDraft({ model })}
          placeholder="YOUR MODEL"
          value={draft.model}
        />
      </Field>
      <Field label="接口地址">
        <TextInput
          ariaLabel="接口地址"
          onChange={(baseUrl) => updateDraft({ baseUrl })}
          placeholder="YOUR BASE URL"
          value={draft.baseUrl}
        />
      </Field>
      <Field label="密钥">
        <TextInput
          ariaLabel="密钥"
          onChange={(apiKey) => updateDraft({ apiKey })}
          placeholder="YOUR API KEY"
          value={draft.apiKey}
        />
      </Field>
    </div>
  );
}

function GenerateDetail({ onBack }: { onBack: () => void }) {
  const settings = useSettings();
  const draft = settings.drafts[settings.card];
  const spec = cardSpec(settings.card);

  return (
    <div className="flex flex-col gap-3">
      <DetailBack onBack={onBack} title="生成" />
      <SwitchRow fallback={spec.draft.stream} label="流式" onChange={(stream) => updateDraft({ stream })} value={draft.stream} />
      <SliderRow
        label="温度"
        max={2}
        onChange={(temperature) => updateDraft({ temperature })}
        step={0.1}
        value={draft.temperature}
      />
      <SliderRow label="top_p" max={1} onChange={(topP) => updateDraft({ topP })} step={0.05} value={draft.topP} />
      <Field black hint="留空表示不设置，用提供者自己的默认值。" label="单次最多生成">
        <TextInput
          ariaLabel="单次最多生成"
          inputMode="numeric"
          onChange={(maxTokens) => {
            if (maxTokens === "" || /^\d+$/.test(maxTokens)) updateDraft({ maxTokens });
          }}
          placeholder="不设置"
          value={draft.maxTokens}
        />
        {draft.maxTokens !== spec.draft.maxTokens ? (
          <Restore onClick={() => updateDraft({ maxTokens: spec.draft.maxTokens })} />
        ) : null}
      </Field>
    </div>
  );
}

function ThinkingDetail({ onBack }: { onBack: () => void }) {
  const settings = useSettings();
  const draft = settings.drafts[settings.card];

  return (
    <div className="flex flex-col gap-3">
      <DetailBack onBack={onBack} title="思考" />
      <SwitchRow fallback={null} label="思考" onChange={(thinking) => updateDraft({ thinking })} value={draft.thinking} />
      <Field label="思考力度">
        <div className="grid grid-cols-4 gap-2">
          {(
            [
              ["", "默认"],
              ["low", "低"],
              ["medium", "中"],
              ["high", "高"],
            ] as const
          ).map(([id, label]) => (
            <Choice
              key={id || "default"}
              label={label}
              onClick={() => updateDraft({ reasoning: id })}
              selected={draft.reasoning === id}
            />
          ))}
        </div>
      </Field>
      <SwitchRow
        fallback={null}
        label="并行工具调用"
        onChange={(parallelTools) => updateDraft({ parallelTools })}
        value={draft.parallelTools}
      />
    </div>
  );
}

function SettingRow({
  detail,
  onClick,
  title,
  value,
}: {
  detail: string;
  onClick: () => void;
  title: string;
  value: string;
}) {
  return (
    <button
      className="flex w-full cursor-pointer items-center gap-3 border-0 text-left"
      onClick={onClick}
      style={{ padding: "12px 14px", background: "transparent", color: ink }}
      type="button"
    >
      <span className="min-w-0 flex-1">
        <span style={{ display: "block", fontSize: 15, lineHeight: "20px" }}>{title}</span>
        <span style={{ display: "block", marginTop: 2, fontSize: 12, lineHeight: "16px", color: quiet }}>{detail}</span>
      </span>
      <span
        className="shrink-0"
        style={{
          maxWidth: "38%",
          overflow: "hidden",
          fontSize: 13,
          lineHeight: "18px",
          color: quiet,
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {value}
      </span>
      <Chevron />
    </button>
  );
}

function SettingList<Id extends string>({
  onOpen,
  rows,
}: {
  onOpen: (id: Id) => void;
  rows: Array<{ id: Id; title: string; detail: string; value: string }>;
}) {
  return (
    <div className="overflow-hidden" style={{ borderRadius: 16, background: "rgba(255,255,255,0.42)" }}>
      {rows.map((row, index) => (
        <div key={row.id} style={{ borderTop: index === 0 ? undefined : "1px solid rgba(28,28,30,0.08)" }}>
          <SettingRow detail={row.detail} onClick={() => onOpen(row.id)} title={row.title} value={row.value} />
        </div>
      ))}
    </div>
  );
}

function DetailBack({ onBack, page = "模型设置", title }: { onBack: () => void; page?: string; title: string }) {
  return (
    <button
      aria-label={`返回${page}，${title}`}
      className="flex cursor-pointer items-center gap-2 border-0 bg-transparent p-0 text-left"
      onClick={onBack}
      style={{ width: "fit-content", color: ink, fontSize: 17, fontWeight: 600, lineHeight: "22px" }}
      type="button"
    >
      <Chevron direction="left" />
      {title}
    </button>
  );
}

function Chevron({ direction = "right" }: { direction?: "left" | "right" }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height="14"
      style={{ flexShrink: 0, transform: direction === "left" ? "rotate(180deg)" : undefined }}
      viewBox="0 0 8 14"
      width="8"
    >
      <path d="M1 1.5L6.5 7L1 12.5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" />
    </svg>
  );
}

function switchText(value: boolean | null) {
  if (value === null) return "默认";
  return value ? "开" : "关";
}

const stepLabel: Record<string, string> = {
  idle: "空闲",
  ask_model: "问模型",
  using_model: "占用核",
  wait_tool: "等工具",
  wait_helpers: "等帮手",
  answer: "回答",
  done: "结束",
};

const extraLabel: Record<string, string> = {
  call_id: "调用编号",
  operation: "操作",
  path: "路径",
  waiting: "正在等",
};

type ContextSection = "registers" | "window";

function ContextPage({ lines, processes, tasks }: { lines: string[]; processes: UiProcess[]; tasks: UiTask[] }) {
  const settings = useSettings();
  const installed = useInstalledApps();
  const [section, setSection] = useState<ContextSection | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const model = settings.drafts[settings.card].model.trim();
  const limit = contextLimit(model);
  const occupied = occupiedTokens(
    loadedPromptText(installed.map((app) => app.id), settings.promptOverrides),
    lines,
  );

  useEffect(() => {
    rootRef.current?.parentElement?.scrollTo({ top: 0 });
  }, [section]);

  return (
    <div className="flex flex-col gap-3" ref={rootRef}>
      {section === null ? (
        <SettingList
          onOpen={setSection}
          rows={[
            {
              id: "registers",
              title: "寄存器",
              detail: "程序计数器和这一拍的小抄",
              value: tasks.length ? `${tasks.length} 条任务` : "空着",
            },
            {
              id: "window",
              title: "这次窗口",
              detail: "这一次对话写下的正文",
              value: occupied > 0 ? occupied.toLocaleString("zh-CN") : formatContext(limit),
            },
          ]}
        />
      ) : null}
      {section === "registers" ? (
        <RegistersDetail onBack={() => setSection(null)} processes={processes} tasks={tasks} />
      ) : null}
      {section === "window" ? (
        <WindowDetail limit={limit} lines={lines} model={model} onBack={() => setSection(null)} />
      ) : null}
    </div>
  );
}

function RegistersDetail({
  onBack,
  processes,
  tasks,
}: {
  onBack: () => void;
  processes: UiProcess[];
  tasks: UiTask[];
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = tasks.find((task) => taskKey(task) === selectedId) ?? tasks[0] ?? null;
  const groups = taskGroups(processes, tasks);

  return (
    <div className="flex flex-col gap-3">
      <DetailBack onBack={onBack} page="上下文" title="寄存器" />
      <p style={{ margin: 0, fontSize: 15, lineHeight: "22px" }}>
        每条任务自己带程序计数器和这些小抄。整本对话留在记忆里。
      </p>
      {tasks.length === 0 ? (
        <p style={{ margin: 0, fontSize: 15, lineHeight: "22px", color: quiet }}>
          现在没有任务。你发出一句话之后，这里会写出它走到哪、纸条上写了什么。
        </p>
      ) : null}
      {groups.map((group) => (
        <div className="flex flex-col gap-1.5" key={group.pid}>
          <span style={{ fontSize: 13, lineHeight: "18px", color: quiet }}>
            {group.capability ? `${group.pid} · ${group.capability}` : group.pid}
          </span>
          {group.tasks.map((task) => {
            const current = selected ? taskKey(task) === taskKey(selected) : false;
            const preview = taskPreview(task);
            return (
              <button
                aria-pressed={current}
                className="flex w-full cursor-pointer items-center gap-2 border-0 text-left"
                key={taskKey(task)}
                onClick={() => setSelectedId(taskKey(task))}
                style={{
                  borderRadius: 12,
                  padding: "10px 12px",
                  background: current ? "rgba(255,255,255,0.78)" : "rgba(255,255,255,0.35)",
                  color: ink,
                }}
                type="button"
              >
                <span className="min-w-0 flex-1">
                  <span style={{ display: "block", fontSize: 15, lineHeight: "20px" }}>
                    {task.leader ? "主任务" : task.id}
                  </span>
                  {preview ? (
                    <span
                      style={{
                        display: "block",
                        marginTop: 2,
                        overflow: "hidden",
                        fontSize: 12,
                        lineHeight: "16px",
                        color: quiet,
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {preview}
                    </span>
                  ) : null}
                </span>
                <span style={{ flexShrink: 0, fontSize: 13, lineHeight: "18px", color: quiet }}>{labelOf(task.pc)}</span>
              </button>
            );
          })}
        </div>
      ))}
      {selected ? <TaskNotes task={selected} /> : null}
    </div>
  );
}

function TaskNotes({ task }: { task: UiTask }) {
  const error = registerText(task.registers.error);
  const extras = extraNotes(task.registers);
  return (
    <div className="flex flex-col gap-3">
      <span style={{ fontSize: 13, lineHeight: "18px", color: quiet }}>程序计数器</span>
      <StepTrack pc={task.pc} />
      <div className="grid grid-cols-2 gap-2">
        <NoteCard
          emphasized={task.changed.includes("question")}
          label="原话"
          name="question"
          value={registerText(task.registers.question)}
          clamp
        />
        <NoteCard
          emphasized={task.changed.includes("command")}
          label="命令"
          name="command"
          value={commandText(task.registers.command)}
        />
        <NoteCard
          emphasized={task.changed.includes("tool")}
          label="工具"
          name="tool"
          value={registerText(task.registers.tool)}
        />
      </div>
      <NoteCard
        emphasized={!error && task.changed.includes("result") && Boolean(registerText(task.registers.result))}
        label="结果"
        name="result"
        value={registerText(task.registers.result)}
        blank
      />
      <NoteCard emphasized={Boolean(error)} label="错误" name="error" value={error} blank />
      {extras.length ? (
        <div className="flex flex-col gap-1.5">
          <span style={{ fontSize: 13, lineHeight: "18px", color: quiet }}>其他</span>
          {extras.map((item) => (
            <NoteCard
              emphasized={task.changed.includes(item.key)}
              key={item.key}
              label={item.label}
              name={item.key}
              value={item.value}
            />
          ))}
        </div>
      ) : null}
      <p style={{ margin: 0, fontSize: 12, lineHeight: "16px", color: quiet }}>
        「回答」这个名字留着，内核现在直接记成结束。
      </p>
    </div>
  );
}

function StepTrack({ pc }: { pc: string }) {
  const steps = [
    { id: "idle", label: "空闲" },
    { id: "ask_model", label: "问模型" },
    { id: "using_model", label: "占用核" },
  ];
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {steps.map((step, index) => (
        <span className="flex items-center gap-1.5" key={step.id}>
          {index > 0 ? <TrackMark /> : null}
          <StepPill current={pc === step.id} label={step.label} />
        </span>
      ))}
      <TrackMark />
      <StepPill current={pc === "wait_tool"} label="等工具" />
      <span style={{ fontSize: 13, lineHeight: "18px", color: quiet }}>/</span>
      <StepPill current={pc === "wait_helpers"} label="等帮手" />
      <TrackMark />
      <StepPill current={pc === "done"} label="结束" />
    </div>
  );
}

function StepPill({ current, label }: { current: boolean; label: string }) {
  return (
    <span
      style={{
        borderRadius: 999,
        padding: "4px 10px",
        background: current ? "rgba(28,28,30,0.88)" : "rgba(255,255,255,0.35)",
        color: current ? "#fff" : ink,
        fontSize: 13,
        lineHeight: "18px",
      }}
    >
      {label}
    </span>
  );
}

function TrackMark() {
  return <span style={{ fontSize: 13, lineHeight: "18px", color: quiet }}>→</span>;
}

function NoteCard({
  blank = false,
  clamp = false,
  emphasized,
  label,
  name,
  value,
}: {
  blank?: boolean;
  clamp?: boolean;
  emphasized: boolean;
  label: string;
  name: string;
  value: string;
}) {
  const empty = !value;
  const shown = empty ? (blank ? "" : "这一拍还没写") : value;
  return (
    <div
      style={{
        ...rowStyle,
        width: "auto",
        background: emphasized ? "rgba(255,255,255,0.86)" : rowStyle.background,
        boxShadow: emphasized ? "inset 0 0 0 1.5px rgba(28,28,30,0.85)" : undefined,
      }}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span style={{ fontSize: 15, lineHeight: "20px" }}>{label}</span>
        <span style={{ fontSize: 12, lineHeight: "16px", color: quiet }}>{name}</span>
      </div>
      <div
        title={empty ? undefined : value}
        style={{
          marginTop: 4,
          fontSize: 13,
          lineHeight: "18px",
          color: empty ? quiet : ink,
          whiteSpace: clamp ? "normal" : "pre-wrap",
          overflow: "hidden",
          display: clamp ? "-webkit-box" : "block",
          WebkitBoxOrient: clamp ? "vertical" : undefined,
          WebkitLineClamp: clamp ? 2 : undefined,
          wordBreak: "break-word",
        }}
      >
        {shown || "\u00a0"}
      </div>
    </div>
  );
}

function taskGroups(processes: UiProcess[], tasks: UiTask[]) {
  const byPid = new Map<string, UiTask[]>();
  for (const task of tasks) {
    const list = byPid.get(task.pid) ?? [];
    list.push(task);
    byPid.set(task.pid, list);
  }
  for (const list of byPid.values()) {
    list.sort((left, right) => Number(right.leader) - Number(left.leader) || left.id.localeCompare(right.id, undefined, { numeric: true }));
  }
  const ordered: Array<{ pid: string; capability: string; tasks: UiTask[] }> = [];
  const seen = new Set<string>();
  for (const process of processes) {
    const group = byPid.get(process.id);
    if (!group) continue;
    seen.add(process.id);
    ordered.push({ capability: process.capability, pid: process.id, tasks: group });
  }
  for (const [pid, group] of byPid) {
    if (seen.has(pid)) continue;
    ordered.push({ capability: "", pid, tasks: group });
  }
  return ordered;
}

function taskKey(task: UiTask): string {
  return `${task.pid}:${task.id}`;
}

function taskPreview(task: UiTask): string {
  const tool = registerText(task.registers.tool);
  if (tool) return tool;
  const question = registerText(task.registers.question);
  return question.length > 18 ? `${question.slice(0, 18)}…` : question;
}

function labelOf(pc: string): string {
  return stepLabel[pc] ?? pc;
}

function commandText(value: unknown): string {
  const text = registerText(value);
  if (!text) return "";
  const head = text.split(" -- ")[0] ?? text;
  const parts = head.trim().split(/\s+/);
  if (parts[0] === "model" && parts[1] === "run") return "让模型看当前这句话";
  return text;
}

function extraNotes(registers: Record<string, unknown>) {
  const known = new Set(["question", "command", "tool", "result", "error"]);
  return Object.entries(registers).flatMap(([key, value]) => {
    if (known.has(key)) return [];
    const text = registerText(value);
    if (!text) return [];
    return [{ key, label: extraLabel[key] ?? key, value: text }];
  });
}

function registerText(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map((item) => registerText(item)).filter(Boolean).join("、");
  return "";
}

function WindowDetail({
  limit,
  lines,
  model,
  onBack,
}: {
  limit: number;
  lines: string[];
  model: string;
  onBack: () => void;
}) {
  const installed = useInstalledApps();
  const settings = useSettings();
  const occupied = occupiedTokens(
    loadedPromptText(installed.map((app) => app.id), settings.promptOverrides),
    lines,
  );
  const outputReserve = Math.max(1, Math.floor(limit / 8));
  const safetyMargin = Math.max(1, Math.floor(limit / 50));

  return (
    <div className="flex flex-col gap-3">
      <DetailBack onBack={onBack} page="上下文" title="这次窗口" />
      <p style={{ margin: 0, fontSize: 32, fontWeight: 600, lineHeight: "36px" }}>{occupied.toLocaleString("zh-CN")}</p>
      <p style={{ margin: 0, fontSize: 15, lineHeight: "22px" }}>
        {occupied === 0 ? "这一次还没装文本" : "这次对话里已经写下的正文"}
      </p>
      <span style={{ fontSize: 13, lineHeight: "18px", color: quiet }}>这扇窗口的天花板</span>
      <CeilingRow label="上限" name={model || "未命名模型"} value={limit} />
      <CeilingRow label="输出预留" name="output_reserve" value={outputReserve} />
      <CeilingRow label="安全余量" name="safety_margin" value={safetyMargin} />
      <p style={{ margin: 0, fontSize: 15, lineHeight: "22px" }}>
        这个数只来自当前这一次对话。别的对话各自算自己的。内核发请求时，没被点名的历史仍然留在记忆里；这里显示的是这一次对话写下的正文有多大，不是提供者账单。
      </p>
    </div>
  );
}

function CeilingRow({ label, name, value }: { label: string; name: string; value: number }) {
  return (
    <div className="flex items-baseline justify-between gap-3" style={{ ...rowStyle, width: "auto" }}>
      <span style={{ fontSize: 15, lineHeight: "20px" }}>{label}</span>
      <span className="min-w-0 flex-1 truncate" style={{ fontSize: 12, lineHeight: "16px", color: quiet }}>
        {name}
      </span>
      <span style={{ flexShrink: 0, fontSize: 15, lineHeight: "20px" }}>{value.toLocaleString("zh-CN")}</span>
    </div>
  );
}

type MemorySection = "store" | "prompt";

function MemoryPage() {
  const settings = useSettings();
  const installed = useInstalledApps();
  const installedIds = installed.map((app) => app.id);
  const [section, setSection] = useState<MemorySection | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const backend = settings.memoryBackend === "local" ? "本地" : "内存";

  useEffect(() => {
    rootRef.current?.parentElement?.scrollTo({ top: 0 });
  }, [section]);

  return (
    <div className="flex flex-col gap-3" ref={rootRef}>
      {section === null ? (
        <SettingList
          onOpen={setSection}
          rows={[
            { id: "store", title: "存放", detail: "进程内存储，或本地文件夹", value: backend },
            { id: "prompt", title: "系统提示", detail: "已下载循环加载的提示词", value: installedLoopLabel(installedIds) },
          ]}
        />
      ) : null}
      {section === "store" ? <StoreDetail onBack={() => setSection(null)} /> : null}
      {section === "prompt" ? <PromptDetail onBack={() => setSection(null)} /> : null}
    </div>
  );
}

function StoreDetail({ onBack }: { onBack: () => void }) {
  const settings = useSettings();
  const session = useKernelSession();

  const applyMemory = (backend: "memory" | "local", path = "") => {
    if (backend === "local" && !path.trim()) return;
    session.actions.configureMemory(
      backend === "local" ? { backend, path: path.trim() } : { backend },
    );
  };

  return (
    <div className="flex flex-col gap-3">
      <DetailBack onBack={onBack} page="记忆" title="存放" />
      <div className="grid grid-cols-2 gap-2">
        <Choice
          label="内存"
          onClick={() => {
            setMemoryBackend("memory");
            applyMemory("memory");
          }}
          selected={settings.memoryBackend === "memory"}
        />
        <Choice
          label="本地"
          onClick={() => {
            setMemoryBackend("local");
            applyMemory("local", settings.localPath);
          }}
          selected={settings.memoryBackend === "local"}
        />
      </div>
      {settings.memoryBackend === "local" ? (
        <Field hint="下次启动生效" label="文件夹路径">
          <TextInput
            ariaLabel="文件夹路径"
            onBlur={(path) => applyMemory("local", path)}
            onChange={setLocalPath}
            placeholder="例如 D:\linope-memory"
            value={settings.localPath}
          />
        </Field>
      ) : null}
    </div>
  );
}

function PromptDetail({ onBack }: { onBack: () => void }) {
  const installed = useInstalledApps();
  const settings = useSettings();
  const loops = installedLoops(installed.map((app) => app.id));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = loops.find((loop) => loop.id === selectedId) ?? null;

  useEffect(() => {
    rootRef.current?.parentElement?.scrollTo({ top: 0 });
  }, [selectedId]);

  return (
    <div className="flex flex-col gap-3" ref={rootRef}>
      {selected ? (
        <PromptEditor
          loop={selected}
          onBack={() => setSelectedId(null)}
          saved={promptText(selected, settings.promptOverrides)}
          edited={selected.id in settings.promptOverrides}
        />
      ) : (
        <>
          <DetailBack onBack={onBack} page="记忆" title="系统提示" />
          {loops.length === 0 ? (
            <p style={{ margin: 0, fontSize: 15, lineHeight: "22px" }}>还没有下载的循环</p>
          ) : (
            <div className="grid grid-cols-2 justify-items-center gap-x-4 gap-y-3">
              {loops.map((loop) => (
                <PromptCard
                  edited={loop.id in settings.promptOverrides}
                  key={loop.id}
                  name={loop.name}
                  onOpen={() => setSelectedId(loop.id)}
                  text={promptText(loop, settings.promptOverrides)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function PromptCard({
  edited,
  name,
  onOpen,
  text,
}: {
  edited: boolean;
  name: string;
  onOpen: () => void;
  text: string;
}) {
  return (
    <div className="flex w-full max-w-[210px] flex-col gap-1.5">
      <div
        aria-label={`${name} 系统提示`}
        className="cursor-pointer overflow-hidden"
        onClick={onOpen}
        onKeyDown={(event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          onOpen();
        }}
        role="button"
        style={{ aspectRatio: "3 / 4", borderRadius: 12, background: "#fff" }}
        tabIndex={0}
      >
        <div
          aria-hidden="true"
          inert
          style={{
            padding: "12px 14px",
            pointerEvents: "none",
            transform: "scale(0.34)",
            transformOrigin: "top left",
            width: "294%",
          }}
        >
          <MessageMarkdown source={text} />
        </div>
      </div>
      <span style={{ fontSize: 13, lineHeight: "18px", textAlign: "center" }}>{name}</span>
      {edited ? (
        <span style={{ fontSize: 12, lineHeight: "16px", color: quiet, textAlign: "center" }}>已修改</span>
      ) : null}
    </div>
  );
}

function PromptEditor({
  edited,
  loop,
  onBack,
  saved,
}: {
  edited: boolean;
  loop: LoadedLoop;
  onBack: () => void;
  saved: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(saved);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    setPromptOverride(loop.id, draft);
    const result = await stagePrompt(loop.capability, draft);
    setNotice(promptFileNotice(result, false));
    setEditing(false);
    setBusy(false);
  };

  const restore = async () => {
    setBusy(true);
    setPromptOverride(loop.id, null);
    forgetFixedPrompts(loop.capability);
    setDraft(loop.text);
    setEditing(false);
    const result = await stagePrompt(loop.capability, null);
    setNotice(promptFileNotice(result, true));
    setBusy(false);
  };

  return (
    <div className="flex flex-col gap-3">
      <DetailBack onBack={onBack} page="系统提示" title={loop.name} />
      <p style={{ margin: 0, fontSize: 15, lineHeight: "22px" }}>{loop.note}</p>
      <p style={{ margin: 0, fontSize: 13, lineHeight: "18px", color: quiet }}>
        保存后交给这个循环的进程。下一句问话只带这份提示。
      </p>
      {editing ? (
        <textarea
          aria-label={`${loop.name} 系统提示原文`}
          onChange={(event) => setDraft(event.target.value)}
          spellCheck={false}
          style={{
            ...inputStyle,
            minHeight: 280,
            resize: "vertical",
            whiteSpace: "pre-wrap",
            fontFamily: "inherit",
          }}
          value={draft}
        />
      ) : (
        <div aria-label={`${loop.name} 系统提示`} style={{ ...inputStyle, padding: 12 }}>
          <MessageMarkdown source={saved} />
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        {editing ? (
          <>
            <PromptAction disabled={busy} label="保存" onClick={() => void save()} />
            <PromptAction
              disabled={busy}
              label="取消"
              onClick={() => {
                setDraft(saved);
                setEditing(false);
              }}
            />
          </>
        ) : (
          <PromptAction
            disabled={busy}
            label="修改"
            onClick={() => {
              setDraft(saved);
              setNotice("");
              setEditing(true);
            }}
          />
        )}
        {edited && !editing ? <PromptAction disabled={busy} label="恢复默认" onClick={() => void restore()} /> : null}
      </div>
      {notice ? <p style={{ margin: 0, fontSize: 13, lineHeight: "18px", color: quiet }}>{notice}</p> : null}
    </div>
  );
}

function PromptAction({
  disabled = false,
  label,
  onClick,
}: {
  disabled?: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className="cursor-pointer border-0"
      disabled={disabled}
      onClick={onClick}
      style={{
        borderRadius: 12,
        padding: "8px 12px",
        background: "rgba(255,255,255,0.55)",
        color: ink,
        fontSize: 15,
        lineHeight: "20px",
        opacity: disabled ? 0.45 : 1,
      }}
      type="button"
    >
      {label}
    </button>
  );
}

function promptFileNotice(result: "saved" | "local" | "failed", restored: boolean): string {
  if (restored && result === "saved") return "已恢复。已经盖掉的那一节留到该进程结束；新进程使用安装时的原文。";
  if (restored && result === "local") return "已恢复界面上的原文。当前没有桌面后端，还不能交给进程。";
  if (restored) return "界面已恢复原文，删除提示文件没有成功。";
  if (result === "saved") return "已记下。这个循环已有进程时，下一句问话只带这份提示；否则在进程起来后、第一句问话之前加载。";
  if (result === "local") return "这份修改只留在这台界面里，当前没有桌面后端，还不能交给进程。";
  return "界面已记下修改，写成提示文件没有成功。";
}

async function stagePrompt(capability: string, text: string | null): Promise<"saved" | "local" | "failed"> {
  const api = window.linopeKernel?.prompts;
  if (!api) return "local";
  try {
    await api.stage({ capability, text });
    return "saved";
  } catch {
    return "failed";
  }
}

function DesktopPage() {
  const settings = useSettings();
  const inputRef = useRef<HTMLInputElement>(null);
  const tiles = [
    ...builtinWallpapers.map((item) => ({ id: item.id, name: item.name, src: item.src })),
    ...settings.uploads.map((item) => ({
      id: item.id,
      name: item.name,
      src: wallpaperById(item.id),
    })),
  ];

  return (
    <div className="flex flex-col gap-3">
      <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600, lineHeight: "20px" }}>选择壁纸</h2>
      <div className="grid grid-cols-2 gap-3">
        {tiles.map((item) => (
          <WallpaperTile
            key={item.id}
            name={item.name}
            onClick={() => setWallpaper(item.id)}
            selected={settings.wallpaperId === item.id}
            src={item.src}
          />
        ))}
        <button
          aria-label="上传壁纸"
          className="grid cursor-pointer place-items-center border-0"
          onClick={() => inputRef.current?.click()}
          style={{
            aspectRatio: "16 / 10",
            borderRadius: 14,
            background: "rgba(255,255,255,0.35)",
            color: ink,
            fontSize: 15,
            lineHeight: "20px",
          }}
          type="button"
        >
          上传
        </button>
      </div>
      <input
        accept="image/*"
        aria-hidden="true"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) void addWallpaper(file);
        }}
        ref={inputRef}
        style={{ display: "none" }}
        tabIndex={-1}
        type="file"
      />
    </div>
  );
}

function WallpaperTile({
  name,
  onClick,
  selected,
  src,
}: {
  name: string;
  onClick: () => void;
  selected: boolean;
  src: string | null;
}) {
  return (
    <button
      aria-label={name}
      aria-pressed={selected}
      className="relative cursor-pointer overflow-hidden border-0 p-0"
      onClick={onClick}
      style={{
        aspectRatio: "16 / 10",
        borderRadius: 14,
        boxShadow: selected ? "inset 0 0 0 2px #1c1c1e" : "none",
        background: "rgba(255,255,255,0.35)",
      }}
      type="button"
    >
      {src ? (
        <img
          alt=""
          draggable={false}
          src={src}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : null}
      {selected ? (
        <span
          style={{
            position: "absolute",
            inset: 0,
            boxShadow: "inset 0 0 0 2px #1c1c1e",
            pointerEvents: "none",
          }}
        />
      ) : null}
    </button>
  );
}

function Field({
  black = false,
  children,
  hint,
  label,
}: {
  black?: boolean;
  children: ReactNode;
  hint?: string;
  label: string;
}) {
  const text = black ? "#000" : quiet;
  return (
    <div className="flex flex-col gap-1.5">
      <span style={{ fontSize: 13, lineHeight: "18px", color: text, fontWeight: black ? 600 : 400 }}>{label}</span>
      {children}
      {hint ? (
        <span style={{ fontSize: 12, lineHeight: "16px", color: black ? "#000" : ink, fontWeight: black ? 600 : 400 }}>
          {hint}
        </span>
      ) : null}
    </div>
  );
}

const inputStyle = {
  width: "100%",
  border: 0,
  borderRadius: 12,
  background: fill,
  color: ink,
  fontSize: 15,
  lineHeight: "20px",
  padding: "8px 12px",
  outline: "none",
} as const;

const rowStyle = {
  ...inputStyle,
  width: "auto",
} as const;

function TextInput({
  ariaLabel,
  inputMode,
  onBlur,
  onChange,
  placeholder,
  value,
}: {
  ariaLabel: string;
  inputMode?: "text" | "numeric";
  onBlur?: (value: string) => void;
  onChange: (value: string) => void;
  placeholder?: string;
  value: string;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <input
      aria-label={ariaLabel}
      autoComplete="off"
      className="placeholder:text-[#1c1c1e]"
      inputMode={inputMode}
      onBlur={(event) => {
        setFocused(false);
        onBlur?.(event.currentTarget.value);
      }}
      onChange={(event) => onChange(event.target.value)}
      onFocus={() => setFocused(true)}
      placeholder={focused ? "" : placeholder}
      spellCheck={false}
      style={inputStyle}
      value={value}
    />
  );
}

function Choice({ label, onClick, selected }: { label: string; onClick: () => void; selected: boolean }) {
  return (
    <button
      aria-pressed={selected}
      className="cursor-pointer border-0"
      onClick={onClick}
      style={{
        borderRadius: 12,
        padding: "10px 12px",
        textAlign: "left",
        background: selected ? "rgba(255,255,255,0.78)" : "rgba(255,255,255,0.35)",
        boxShadow: selected ? "inset 0 0 0 1.5px rgba(28,28,30,0.85)" : "none",
        color: ink,
        fontSize: 15,
        lineHeight: "20px",
      }}
      type="button"
    >
      {label}
    </button>
  );
}

function SwitchRow({
  fallback,
  label,
  onChange,
  value,
}: {
  fallback: boolean | null;
  label: string;
  onChange: (value: boolean | null) => void;
  value: boolean | null;
}) {
  const on = value === true;
  const caption = value === null ? "默认" : value ? "开" : "关";
  return (
    <div className="flex items-center justify-between gap-3" style={{ ...rowStyle, width: "100%" }}>
      <span style={{ fontSize: 15, lineHeight: "20px" }}>{label}</span>
      <span className="ml-auto" style={{ fontSize: 13, color: quiet }}>
        {caption}
      </span>
      {value !== fallback ? <Restore onClick={() => onChange(fallback)} /> : null}
      <button
        aria-checked={on}
        aria-label={label}
        className="cursor-pointer border-0 p-0"
        onClick={() => onChange(!on)}
        role="switch"
        style={{
          width: 44,
          height: 26,
          borderRadius: 999,
          background: on ? "#34c759" : "rgba(28,28,30,0.18)",
          padding: 2,
        }}
        type="button"
      >
        <span
          style={{
            display: "block",
            width: 22,
            height: 22,
            borderRadius: 999,
            background: "#fff",
            transform: on ? "translateX(18px)" : "translateX(0)",
            transition: prefersReducedMotion() ? "none" : "transform 0.2s ease",
          }}
        />
      </button>
    </div>
  );
}

function SliderRow({
  label,
  max,
  onChange,
  step,
  value,
}: {
  label: string;
  max: number;
  onChange: (value: number | null) => void;
  step: number;
  value: number | null;
}) {
  const shown = value === null ? max / 2 : value;
  return (
    <div className="flex flex-col gap-2" style={{ ...rowStyle, width: "100%" }}>
      <div className="flex items-center justify-between gap-3">
        <span style={{ fontSize: 15, lineHeight: "20px" }}>{label}</span>
        <span style={{ fontSize: 13, color: quiet }}>{value === null ? "默认" : trimNumber(value)}</span>
        {value !== null ? <Restore onClick={() => onChange(null)} /> : null}
      </div>
      <input
        aria-label={label}
        aria-valuetext={value === null ? "默认" : trimNumber(value)}
        max={max}
        min={0}
        onChange={(event) => onChange(roundStep(Number(event.target.value), step))}
        step={step}
        style={{ width: "100%", accentColor: ink, opacity: value === null ? 0.45 : 1 }}
        type="range"
        value={shown}
      />
    </div>
  );
}

function Restore({ onClick }: { onClick: () => void }) {
  return (
    <button
      className="cursor-pointer border-0 bg-transparent p-0"
      onClick={onClick}
      style={{ fontSize: 13, lineHeight: "18px", color: ink }}
      type="button"
    >
      默认
    </button>
  );
}

function StepButton({
  children,
  disabled,
  label,
  onClick,
}: {
  children: ReactNode;
  disabled?: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={label}
      className="grid cursor-pointer place-items-center border-0"
      disabled={disabled}
      onClick={onClick}
      style={{
        width: 32,
        height: 32,
        borderRadius: 999,
        background: "rgba(255,255,255,0.8)",
        color: ink,
        fontSize: 18,
        opacity: disabled ? 0.35 : 1,
      }}
      type="button"
    >
      {children}
    </button>
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

function roundStep(value: number, step: number) {
  if (!Number.isFinite(value)) return 0;
  return Number((Math.round(value / step) * step).toFixed(2));
}

function trimNumber(value: number) {
  return Number(value.toFixed(2)).toString();
}

function formatContext(limit: number) {
  if (limit < 10000) return limit.toLocaleString("zh-CN");
  const wan = Math.round((limit / 10000) * 10) / 10;
  const text = Number.isInteger(wan) ? String(wan) : wan.toFixed(1);
  return `${text}万`;
}

function SettingsIsland({ active, onRestore }: { active: boolean; onRestore: () => void }) {
  const island = useIslandActions();
  const settings = useSettings();
  const restore = useRef(onRestore);
  restore.current = onRestore;
  const model = settings.drafts[settings.card].model.trim();
  const detail = model ? `${model} · ${formatContext(contextLimit(model))}` : "还没选模型";

  useEffect(() => {
    if (!active) {
      return;
    }
    const handle = island.start({
      id: "settings",
      label: `设置，${detail}`,
      onPress: () => {
        if (island.presentation === "expanded") {
          restore.current();
          return;
        }
        island.expand("settings");
      },
      compact: {
        leading: <span style={islandLine}>设置</span>,
      },
      minimal: <span style={islandLine}>设置</span>,
      expanded: {
        leading: <span style={islandExpandedLine}>设置</span>,
        bottom: <span style={{ ...islandExpandedLine, opacity: 0.62 }}>{detail}</span>,
      },
    });
    return () => handle.end();
  }, [active, island]);

  useEffect(() => {
    if (!active) {
      return;
    }
    island.update("settings", {
      label: `设置，${detail}`,
      expanded: {
        bottom: <span style={{ ...islandExpandedLine, opacity: 0.62 }}>{detail}</span>,
      },
    });
  }, [active, detail, island]);

  return null;
}

export { SettingsBodySlot, SettingsIsland, SettingsLensSlot };
