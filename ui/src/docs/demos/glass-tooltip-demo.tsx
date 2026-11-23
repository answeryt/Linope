import { type CSSProperties, useState } from "react";
import { Bell, Gear, Share } from "@/components/docs/icons";
import { ShowcaseGrid } from "@/components/docs/showcase-grid";
import { Glass } from "@/components/ui/glass";

const STAGE_W = 380;
const STAGE_H = 200;
const SIZE = 52;
const GAP = 26;
const ROW_Y = STAGE_H / 2 - SIZE / 2 + 18;
const TIP_H = 36;
const TIP_GAP = 14;

const ITEMS = [
  { id: "bell", label: "Notifications", Icon: Bell, tipW: 118 },
  { id: "gear", label: "Settings", Icon: Gear, tipW: 86 },
  { id: "share", label: "Share", Icon: Share, tipW: 70 },
];

const TOTAL = ITEMS.length * SIZE + (ITEMS.length - 1) * GAP;
const START = (STAGE_W - TOTAL) / 2;
const ITEM_X = ITEMS.map((_, i) => START + i * (SIZE + GAP));

const frameStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "50%",
  width: STAGE_W,
  height: STAGE_H,
  transform: "translate(-50%, -50%)",
};

const lensShadow =
  "inset 0 1px 1.5px rgba(255,255,255,0.55), 0 14px 30px -12px rgba(0,0,0,0.35)";

function GlassTooltipDemo({ tint }: { tint?: number }) {
  const [hovered, setHovered] = useState<number | null>(0);

  const tip = hovered === null ? null : ITEMS[hovered];
  const tipCx = hovered === null ? 0 : ITEM_X[hovered] + SIZE / 2;
  const tipW = tip?.tipW ?? 0;
  const tipStyle: CSSProperties | null = tip
    ? {
        position: "absolute",
        left: tipCx - tipW / 2,
        top: ROW_Y - TIP_GAP - TIP_H,
        width: tipW,
        height: TIP_H,
        borderRadius: TIP_H / 2,
        boxShadow: lensShadow,
      }
    : null;

  return (
    <div className="absolute inset-0 overflow-hidden rounded-[20px]">
      <Glass
        chroma={0.3}
        className="absolute inset-0"
        depth={9}
        domeDepth={10}
        edgeHighlight={0.3}
        glow={0.12}
        lens={
          <div style={frameStyle}>
            {ITEMS.map((it, i) => (
              <div
                data-glass-lens
                key={it.id}
                style={{
                  position: "absolute",
                  left: ITEM_X[i],
                  top: ROW_Y,
                  width: SIZE,
                  height: SIZE,
                  borderRadius: SIZE / 2,
                  boxShadow: lensShadow,
                }}
              />
            ))}
            {tipStyle ? <div data-glass-lens style={tipStyle} /> : null}
          </div>
        }
        tint={tint}
      >
        <ShowcaseGrid />
      </Glass>

      <div style={frameStyle}>
        {ITEMS.map((it, i) => (
          <button
            aria-label={it.label}
            className="absolute flex cursor-pointer items-center justify-center text-[#1d1d1f] outline-none"
            key={it.id}
            onFocus={() => setHovered(i)}
            onPointerEnter={() => setHovered(i)}
            style={{ left: ITEM_X[i], top: ROW_Y, width: SIZE, height: SIZE }}
            type="button"
          >
            <it.Icon className="size-5" />
          </button>
        ))}
        {tip ? (
          <div
            className="absolute flex items-center justify-center font-medium text-[#1d1d1f] text-[13px]"
            style={{
              left: tipCx - tipW / 2,
              top: ROW_Y - TIP_GAP - TIP_H,
              width: tipW,
              height: TIP_H,
            }}
          >
            {tip.label}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export { GlassTooltipDemo };
