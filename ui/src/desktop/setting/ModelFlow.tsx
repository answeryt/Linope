import { useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  NodeToolbar,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { prefersReducedMotion } from "@/components/ui/glass-motion";
import "./model-flow.css";

const coreWidth = 136;
const coreHeight = 84;
const personWidth = 74;
const personHeight = 36;
const queuePad = 14;
const queueHeader = 26;
const maxShownCores = 4;
const phaseCount = 4;
const phaseMs = 2600;
const stripLength = 12;
const names = ["taskA", "taskB", "taskC", "taskD", "taskE", "taskF", "taskG", "taskH"];

type LaneKind = "queue" | "core" | "waiting" | "person";
type Beat = "run" | "release" | "grant" | "return";
type Cell = "run" | "idle";
type Point = { x: number; y: number };

type LaneNodeData = {
  title: string;
  detail: string;
  kind: LaneKind;
  busy?: boolean;
  strip?: Cell[];
  hidden?: boolean;
};

type LaneNodeType = Node<LaneNodeData, "lane">;

type Frame = {
  ready: string[];
  cores: Array<string | null>;
  waiting: string[];
  beat: Beat;
  caption: string;
  serving: string;
  queued: string;
  focus: string;
};

const nodeTypes = { lane: LaneNode };
const beats: Beat[] = ["run", "release", "grant", "return"];

function shownCount(cores: number) {
  return Math.min(Math.max(cores, 1), maxShownCores);
}

function flowHeight() {
  return 360;
}

function beatOf(tick: number): Beat {
  const step = ((tick % phaseCount) + phaseCount) % phaseCount;
  return beats[step] ?? "run";
}

function stageFor(shown: number) {
  const queueWidth = queuePad + coreWidth + 12 + personWidth + queuePad;
  const queueHeight = queueHeader + queuePad + coreHeight + queuePad;
  const queueX = 12;
  const queueY = 84;
  const slotY = queueY + queueHeader + queuePad;
  const personInQueue = {
    x: queueX + (queueWidth - personWidth) / 2,
    y: slotY + (coreHeight - personHeight) / 2,
  };
  const coresX = queueX + queueWidth + 32;
  const home = (index: number): Point => ({
    x: coresX + index * (coreWidth + 14),
    y: slotY,
  });
  const stageRight = home(shown - 1).x + coreWidth;
  const waitingWidth = 168;
  const waitingHeight = 64;
  const waiting = {
    x: Math.max(coresX, stageRight - waitingWidth),
    y: 0,
    width: waitingWidth,
    height: waitingHeight,
  };
  const chipInside = (index: number): Point => {
    const at = home(index);
    return { x: at.x + (coreWidth - personWidth) / 2, y: at.y + 26 };
  };
  const chipWaiting = {
    x: waiting.x + (waitingWidth - personWidth) / 2,
    y: waiting.y + 24,
  };
  return { queueWidth, queueHeight, queueX, queueY, personInQueue, home, waiting, chipInside, chipWaiting };
}

function captionFor(shown: number, beat: Beat, serving: string, queued: string) {
  if (beat === "run") {
    return shown > 1 ? "每个核都在调用模型，没有空转。" : `${serving}正在这个核上调用模型。`;
  }
  if (beat === "release") {
    return shown > 1
      ? `${serving}离开核，在做事。\n这一小段就是空转。`
      : `${serving}离开核，在做事。\n这一小段就是空转。`;
  }
  if (beat === "grant") {
    return shown > 1 ? `${queued}走进核 1，空转被填上。\n其他核一直没停。` : `${queued}走进这个核，空转被填上。`;
  }
  return `${serving}回到队尾。`;
}

function focusCaption(beat: Beat, focus: string) {
  if (beat === "run") return `${focus} 在就绪队列。`;
  if (beat === "release") return `${focus} 进入核 1。`;
  if (beat === "grant") return `${focus} 离开核，在做事。`;
  return `${focus} 回到队尾。`;
}

function frameFor(cores: number, tick: number, focus = ""): Frame {
  const shown = shownCount(cores);
  const beat = beatOf(tick);
  if (focus) {
    const residents = names.filter((name) => name !== focus).slice(0, Math.max(0, shown - 1));
    const inCore = beat === "release";
    const away = beat === "grant";
    return {
      ready: inCore || away ? [] : [focus],
      cores: [inCore ? focus : null, ...residents],
      waiting: away ? [focus] : [],
      beat,
      caption: focusCaption(beat, focus),
      serving: focus,
      queued: "",
      focus,
    };
  }
  const cycle = Math.floor(Math.max(0, tick) / phaseCount);
  const others = names.slice(1, shown);
  const first = names[0] ?? "taskA";
  const next = names[shown] ?? "taskB";
  const serving = cycle % 2 === 0 ? first : next;
  const queued = cycle % 2 === 0 ? next : first;
  const coreHeld = beat === "run" ? serving : beat === "release" ? null : queued;
  const ready = beat === "run" || beat === "release" ? [queued] : beat === "return" ? [serving] : [];
  const waiting = beat === "release" || beat === "grant" ? [serving] : [];
  return {
    ready,
    cores: [coreHeld, ...others],
    waiting,
    beat,
    caption: captionFor(shown, beat, serving, queued),
    serving,
    queued,
    focus: "",
  };
}

function stripFor(coreIndex: number, tick: number, focus: boolean): Cell[] {
  const cells: Cell[] = [];
  for (let step = 0; step <= Math.max(0, tick); step += 1) {
    const onCore = step % phaseCount === 1;
    const idle = coreIndex === 0 && (focus ? !onCore : onCore);
    cells.push(idle ? "idle" : "run");
  }
  return cells.slice(-stripLength);
}

function personSpot(name: string, frame: Frame, stage: ReturnType<typeof stageFor>): Point {
  if (frame.focus && name === frame.focus) {
    if (frame.beat === "release") return stage.chipInside(0);
    if (frame.beat === "grant") return stage.chipWaiting;
    return stage.personInQueue;
  }
  if (name === frame.serving) {
    if (frame.beat === "run") return stage.chipInside(0);
    if (frame.beat === "return") return stage.personInQueue;
    return stage.chipWaiting;
  }
  if (frame.beat === "grant" || frame.beat === "return") return stage.chipInside(0);
  return stage.personInQueue;
}

function personDetail(name: string, frame: Frame) {
  if (frame.focus && name === frame.focus) {
    if (frame.beat === "release") return "在核里";
    if (frame.beat === "grant") return "在做事";
    return "排队";
  }
  if (name === frame.serving) {
    if (frame.beat === "run") return "在核里";
    if (frame.beat === "return") return "排队";
    return "在做事";
  }
  return frame.beat === "grant" || frame.beat === "return" ? "在核里" : "排队";
}

function LaneNode({ data, selected }: NodeProps<LaneNodeType>) {
  if (data.hidden) return <div aria-hidden="true" />;
  const stateClass = data.kind === "core" ? (data.busy ? " is-busy" : " is-idle") : "";
  const label = data.detail ? `${data.title}，${data.detail}` : data.title;
  return (
    <>
      <NodeToolbar isVisible={selected} offset={8} position={Position.Top}>
        <div className="model-flow-toolbar">
          <span>{data.title}</span>
          {data.detail ? <span>{data.detail}</span> : null}
        </div>
      </NodeToolbar>
      <div
        aria-label={label}
        className={`model-flow-node model-flow-node-${data.kind}${stateClass}${selected ? " is-selected" : ""}`}
        role="group"
      >
        {data.kind === "person" ? (
          <span className="model-flow-node-detail">{data.title}</span>
        ) : (
          <>
            <span className="model-flow-node-title">{data.title}</span>
            {data.detail ? <span className="model-flow-node-detail">{data.detail}</span> : null}
            {data.kind === "core" && data.strip ? (
              <span aria-hidden="true" className="model-flow-strip">
                {data.strip.map((cell, index) => (
                  <i className={`model-flow-cell model-flow-cell-${cell}`} key={`${cell}-${index}`} />
                ))}
              </span>
            ) : null}
          </>
        )}
      </div>
    </>
  );
}

function createNodes(frame: Frame, tick: number): LaneNodeType[] {
  const shown = frame.cores.length;
  const stage = stageFor(shown);
  const people = [
    ...frame.cores.slice(1).map((name, index) => ({ name: name ?? "", index: index + 1 })),
    { name: frame.serving, index: -1 },
    { name: frame.queued, index: -1 },
  ];
  return [
    {
      id: "ready",
      type: "lane",
      position: { x: stage.queueX, y: stage.queueY },
      data: { title: "就绪队列", detail: frame.ready.length ? "" : "空", kind: "queue" },
      draggable: false,
      selectable: true,
      connectable: false,
      focusable: false,
      zIndex: 0,
      style: { width: stage.queueWidth, height: stage.queueHeight },
    },
    {
      id: "waiting",
      type: "lane",
      position: { x: stage.waiting.x, y: stage.waiting.y },
      data: { title: "在做事", detail: frame.waiting.length ? "" : "空", kind: "waiting" },
      draggable: false,
      selectable: true,
      connectable: false,
      focusable: false,
      zIndex: 0,
      style: { width: stage.waiting.width, height: stage.waiting.height },
    },
    ...frame.cores.map((task, index) => ({
      id: `core-${index}`,
      type: "lane" as const,
      position: stage.home(index),
      data: {
        title: `模型核 ${index + 1}`,
        detail: task ? "" : "空转",
        kind: "core" as const,
        busy: Boolean(task),
        strip: stripFor(index, tick, Boolean(frame.focus)),
      },
      draggable: false,
      selectable: true,
      connectable: false,
      focusable: false,
      zIndex: 2,
      style: { width: coreWidth, height: coreHeight },
    })),
    ...people.flatMap((person) => {
      if (!person.name) return [];
      const resident = person.index >= 0;
      const width = Math.min(coreWidth - 16, Math.max(personWidth, person.name.length * 8 + 20));
      const spot = resident ? stage.chipInside(person.index) : personSpot(person.name, frame, stage);
      return [
        {
          id: `person-${person.name}`,
          type: "lane" as const,
          position: { x: spot.x + (personWidth - width) / 2, y: spot.y },
          data: {
            title: person.name,
            detail: resident ? "在核里" : personDetail(person.name, frame),
            kind: "person" as const,
          },
          draggable: false,
          selectable: true,
          connectable: false,
          focusable: false,
          zIndex: 5,
          style: { width, height: personHeight },
        },
      ];
    }),
  ];
}

function FitView({ cores, width }: { cores: number; width: number }) {
  const { fitView } = useReactFlow();

  useEffect(() => {
    if (width <= 0) return;
    const frame = requestAnimationFrame(() => {
      void fitView({ padding: 0.12, duration: 0 });
    });
    return () => cancelAnimationFrame(frame);
  }, [cores, fitView, width]);

  return null;
}

function FlowCanvas({ cores, focus, width }: { cores: number; focus: string; width: number }) {
  const reduced = prefersReducedMotion();
  const [tick, setTick] = useState(reduced ? (focus ? 1 : 2) : 0);
  const frame = useMemo(() => frameFor(cores, tick, focus), [cores, focus, tick]);
  const initialNodes = useMemo(() => createNodes(frame, tick), [frame, tick]);
  const [nodes, setNodes, onNodesChange] = useNodesState<LaneNodeType>(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    setNodes(createNodes(frame, tick));
  }, [frame, setNodes, tick]);

  useEffect(() => {
    setTick(reduced ? (focus ? 1 : 2) : 0);
  }, [focus, reduced]);

  useEffect(() => {
    if (reduced) return;
    const timer = window.setInterval(() => {
      setTick((current) => current + 1);
    }, phaseMs);
    return () => window.clearInterval(timer);
  }, [reduced]);

  return (
    <ReactFlow
      edges={edges}
      elementsSelectable
      fitView
      maxZoom={1.5}
      minZoom={0.4}
      nodes={nodes}
      nodesConnectable={false}
      nodesDraggable={false}
      nodeTypes={nodeTypes}
      onEdgesChange={onEdgesChange}
      onNodesChange={onNodesChange}
      panOnDrag
      proOptions={{ hideAttribution: false }}
      zoomOnDoubleClick={false}
      zoomOnPinch
      zoomOnScroll
    >
      <Background color="rgba(28,28,30,0.09)" gap={18} size={1} />
      <Panel position="top-left">
        <div className="model-flow-panel">
          <strong>模型核调度</strong>
          <span className="model-flow-caption">{frame.caption}</span>
          <span className="model-flow-legend">
            <i className="model-flow-cell model-flow-cell-run" />
            绿 = 调用
            <i className="model-flow-cell model-flow-cell-idle" />
            灰 = 空转
          </span>
        </div>
      </Panel>
      <FitView cores={cores} width={width} />
    </ReactFlow>
  );
}

function ModelFlow({ cores, focus = "" }: { cores: number; focus?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const height = flowHeight();

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(() => setWidth(element.clientWidth));
    observer.observe(element);
    setWidth(element.clientWidth);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      aria-label="模型核调度示意"
      className="model-flow"
      onWheel={(event) => event.stopPropagation()}
      ref={ref}
      style={{ height }}
    >
      <ReactFlowProvider>
        <FlowCanvas cores={cores} focus={focus} width={width} />
      </ReactFlowProvider>
    </div>
  );
}

export { ModelFlow };
