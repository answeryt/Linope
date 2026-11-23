import { type PointerEvent as ReactPointerEvent, useMemo, useRef, useState } from "react";
import { DocPage } from "@/components/docs/doc-page";
import { ShowcaseGrid } from "@/components/docs/showcase-grid";
import { Glass, generateLensMap } from "@/components/ui/glass";

const STAGE_W = 342;
const STAGE_H = 320;

interface Params {
  width: number;
  height: number;
  borderRadius: number;
  scale: number;
  depth: number;
  curvature: number;
  splay: number;
  chroma: number;
  blur: number;
  glow: number;
  edgeHighlight: number;
  specularAngle: number;
  tint: number;
}

const DEFAULTS: Params = {
  width: 70,
  height: 60,
  borderRadius: 28,
  scale: 0.1,
  depth: 10,
  curvature: 40,
  splay: 1,
  chroma: 0.2,
  blur: 0,
  glow: 0.1,
  edgeHighlight: 0.25,
  specularAngle: 45,
  tint: 0,
};

interface RowProps {
  label: string;
  value: string;
  min: number;
  max: number;
  step: number;
  raw: number;
  onChange: (v: number) => void;
}

function Row({ label, value, min, max, step, raw, onChange }: RowProps) {
  const pct = ((raw - min) / (max - min)) * 100;
  return (
    <div className="grid grid-cols-[110px_1fr_44px] items-center gap-3">
      <span className="text-[13px] text-muted-foreground">{label}</span>
      <input
        className="docs-range w-full"
        max={max}
        min={min}
        onChange={(e) => onChange(Number(e.target.value))}
        step={step}
        style={{
          background: `linear-gradient(to right, #a8a2f5 0 ${pct}%, color-mix(in srgb, var(--muted-foreground) 25%, transparent) ${pct}% 100%)`,
        }}
        type="range"
        value={raw}
      />
      <span className="text-right font-mono text-[13px] text-foreground/85 tabular-nums">
        {value}
      </span>
    </div>
  );
}

function PlaygroundPage() {
  const [p, setP] = useState<Params>(DEFAULTS);
  const [pos, setPos] = useState({ x: 0.5, y: 0.5 });
  const dragOffset = useRef<{ dx: number; dy: number } | null>(null);
  const set = <K extends keyof Params>(key: K) => (v: number) =>
    setP((prev) => ({ ...prev, [key]: v }));

  const lensW = p.width * 2;
  const lensH = p.height * 2;

  const mapUrl = useMemo(
    () =>
      generateLensMap({
        halfW: p.width,
        halfH: p.height,
        radius: p.borderRadius,
        depth: p.depth,
        domeDepth: p.curvature,
        splay: p.splay,
        glowStrength: p.glow,
        glowSpread: 1,
        glowExponent: 1.5,
        edgeStrength: p.edgeHighlight,
        edgeWidth: 3,
        edgeExponent: 1.5,
        specularAngle: p.specularAngle,
        size: 512,
      }),
    [p]
  );

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const rx = (e.clientX - rect.left) / rect.width;
    const ry = (e.clientY - rect.top) / rect.height;
    e.preventDefault();
    dragOffset.current = { dx: rx - pos.x, dy: ry - pos.y };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragOffset.current) {
      return;
    }
    e.preventDefault();
    const rect = e.currentTarget.getBoundingClientRect();
    const rx = (e.clientX - rect.left) / rect.width;
    const ry = (e.clientY - rect.top) / rect.height;
    const { dx, dy } = dragOffset.current;
    setPos({
      x: Math.max(0, Math.min(1, rx - dx)),
      y: Math.max(0, Math.min(1, ry - dy)),
    });
  };
  const onPointerUp = () => {
    dragOffset.current = null;
  };
  const dragProps = {
    onPointerCancel: onPointerUp,
    onPointerDown,
    onPointerMove,
    onPointerUp,
  };

  return (
    <DocPage
      description="Every parameter of the lens engine, live. Drag the lens around, then watch the displacement map on the right update with it."
      title="Playground"
    >
      <div className="mt-8 flex flex-wrap justify-center gap-4 lg:justify-start">
        <div
          {...dragProps}
          className="relative max-w-full cursor-grab touch-none select-none overflow-hidden rounded-[32px] active:cursor-grabbing"
          style={{ width: STAGE_W, height: STAGE_H }}
        >
          <Glass
            blur={p.blur}
            chroma={p.chroma}
            className="absolute inset-0"
            depth={p.depth}
            domeDepth={p.curvature}
            edgeHighlight={p.edgeHighlight}
            glow={p.glow}
            lens={
              <div
                data-glass-lens
                style={{
                  position: "absolute",
                  left: pos.x * STAGE_W - lensW / 2,
                  top: pos.y * STAGE_H - lensH / 2,
                  width: lensW,
                  height: lensH,
                  borderRadius: p.borderRadius,
                  boxShadow:
                    "0 0 0 1px rgba(255, 255, 255, 0.3), 0 8px 24px rgba(0, 0, 0, 0.4)",
                }}
              />
            }
            mapSize={512}
            scaleX={p.scale}
            scaleY={p.scale}
            specularAngle={p.specularAngle}
            specularStrength={0}
            splay={p.splay}
            tint={p.tint}
          >
            <ShowcaseGrid />
          </Glass>
        </div>

        <div
          {...dragProps}
          className="relative max-w-full cursor-grab touch-none select-none overflow-hidden rounded-[32px] active:cursor-grabbing"
          style={{ width: STAGE_W, height: STAGE_H, background: "#808080" }}
        >
          {mapUrl ? (
            <img
              alt="Generated displacement map at the lens position"
              className="pointer-events-none absolute block"
              draggable={false}
              src={mapUrl}
              style={{
                left: `${pos.x * 100}%`,
                top: `${pos.y * 100}%`,
                transform: "translate(-50%, -50%)",
                width: lensW,
                height: lensH,
              }}
            />
          ) : null}
        </div>
      </div>
      <p className="mt-3 text-[13px] text-muted-foreground">
        On the left is the refracted result, on the right the map that drives
        it.
      </p>

      <div className="mt-5 rounded-[18px] border border-border bg-card p-5">
        <div className="grid gap-x-10 gap-y-3 md:grid-cols-2">
          <div className="flex flex-col gap-3">
            <Row label="Width" max={120} min={20} onChange={set("width")} raw={p.width} step={1} value={String(p.width)} />
            <Row label="Border radius" max={64} min={0} onChange={set("borderRadius")} raw={p.borderRadius} step={1} value={String(p.borderRadius)} />
            <Row label="Depth" max={60} min={5} onChange={set("depth")} raw={p.depth} step={1} value={String(p.depth)} />
            <Row label="Splay" max={1} min={0} onChange={set("splay")} raw={p.splay} step={0.01} value={p.splay.toFixed(2)} />
            <Row label="Blur" max={2} min={0} onChange={set("blur")} raw={p.blur} step={0.25} value={p.blur.toFixed(2)} />
            <Row label="Edge highlight" max={1} min={0} onChange={set("edgeHighlight")} raw={p.edgeHighlight} step={0.01} value={p.edgeHighlight.toFixed(2)} />
            <Row label="Tint" max={1} min={0} onChange={set("tint")} raw={p.tint} step={0.01} value={p.tint.toFixed(2)} />
          </div>
          <div className="flex flex-col gap-3">
            <Row label="Height" max={80} min={20} onChange={set("height")} raw={p.height} step={1} value={String(p.height)} />
            <Row label="Scale" max={0.2} min={0} onChange={set("scale")} raw={p.scale} step={0.001} value={p.scale.toFixed(3)} />
            <Row label="Curvature" max={80} min={0} onChange={set("curvature")} raw={p.curvature} step={1} value={String(p.curvature)} />
            <Row label="Chroma" max={1} min={0} onChange={set("chroma")} raw={p.chroma} step={0.01} value={p.chroma.toFixed(2)} />
            <Row label="Glow" max={1} min={0} onChange={set("glow")} raw={p.glow} step={0.01} value={p.glow.toFixed(2)} />
            <Row label="Specular angle" max={180} min={0} onChange={set("specularAngle")} raw={p.specularAngle} step={1} value={String(p.specularAngle)} />
          </div>
        </div>
      </div>
    </DocPage>
  );
}

export { PlaygroundPage };
