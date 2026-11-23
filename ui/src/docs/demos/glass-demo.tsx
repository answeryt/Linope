import { type PointerEvent, useRef, useState } from "react";
import { ShowcaseGrid } from "@/components/docs/showcase-grid";
import { Glass } from "@/components/ui/glass";

const LENS_W = 150;
const LENS_H = 110;

function GlassDemo({ tint }: { tint?: number }) {
  const [pos, setPos] = useState({ x: 0.5, y: 0.5 });
  const grab = useRef<{ dx: number; dy: number } | null>(null);

  const toLocal = (e: PointerEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    };
  };

  return (
    <div
      className="absolute inset-0 cursor-grab touch-none select-none overflow-hidden rounded-[20px] active:cursor-grabbing"
      onPointerCancel={() => {
        grab.current = null;
      }}
      onPointerDown={(e) => {
        const p = toLocal(e);
        grab.current = { dx: p.x - pos.x, dy: p.y - pos.y };
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (!grab.current) {
          return;
        }
        const p = toLocal(e);
        setPos({
          x: Math.min(1, Math.max(0, p.x - grab.current.dx)),
          y: Math.min(1, Math.max(0, p.y - grab.current.dy)),
        });
      }}
      onPointerUp={() => {
        grab.current = null;
      }}
    >
      <Glass
        chroma={0.3}
        className="absolute inset-0"
        depth={12}
        domeDepth={40}
        edgeHighlight={0.3}
        glow={0.12}
        lens={
          <div
            data-glass-lens
            style={{
              position: "absolute",
              left: `calc(${pos.x * 100}% - ${LENS_W / 2}px)`,
              top: `calc(${pos.y * 100}% - ${LENS_H / 2}px)`,
              width: LENS_W,
              height: LENS_H,
              borderRadius: 32,
              boxShadow:
                "inset 0 1px 1px rgba(255,255,255,0.6), 0 14px 34px -10px rgba(60,40,140,0.45)",
            }}
          />
        }
        scaleX={0.1}
        scaleY={0.1}
        tint={tint}
      >
        <ShowcaseGrid />
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-[#1f2c49]">
          <span className="font-semibold text-[30px] tracking-tight">
            liquid glass
          </span>
          <span className="text-[13px] opacity-70">
            drag the lens, it refracts this live DOM
          </span>
        </div>
      </Glass>
    </div>
  );
}

export { GlassDemo };
