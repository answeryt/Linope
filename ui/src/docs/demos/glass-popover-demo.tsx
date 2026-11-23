import { type CSSProperties, type ReactNode, useState } from "react";
import { Ellipsis, Pencil, Share } from "@/components/docs/icons";
import { ShowcaseGrid } from "@/components/docs/showcase-grid";
import { Glass } from "@/components/ui/glass";

const STAGE_W = 300;
const STAGE_H = 320;
const TRIGGER = 44;
const POP = { left: 16, top: 16 + TRIGGER + 12, width: 250, height: 116, radius: 26 };

const frameStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "50%",
  width: STAGE_W,
  height: STAGE_H,
  transform: "translate(-50%, -50%)",
};

const lensShadow =
  "inset 0 1px 1.5px rgba(255,255,255,0.55), 0 18px 44px -14px rgba(0,0,0,0.32)";

function MenuRow({
  icon,
  label,
  sublabel,
}: {
  icon: ReactNode;
  label: string;
  sublabel?: string;
}) {
  return (
    <div className="mx-2.5 flex items-center gap-4 rounded-[14px] px-3 py-2.5 text-[#1d1d1f]">
      <span className="inline-flex w-6 shrink-0 items-center justify-center [&_svg]:size-5">
        {icon}
      </span>
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-[16px] leading-tight">{label}</span>
        {sublabel ? (
          <span className="truncate text-[13px] leading-tight opacity-55">
            {sublabel}
          </span>
        ) : null}
      </span>
    </div>
  );
}

function GlassPopoverDemo({ tint }: { tint?: number }) {
  const [open, setOpen] = useState(true);

  const triggerLens: CSSProperties = {
    position: "absolute",
    left: 16,
    top: 16,
    width: TRIGGER,
    height: TRIGGER,
    borderRadius: TRIGGER / 2,
    boxShadow: lensShadow,
  };
  const popLens: CSSProperties = {
    position: "absolute",
    left: POP.left,
    top: POP.top,
    width: POP.width,
    height: POP.height,
    borderRadius: POP.radius,
    boxShadow: lensShadow,
  };

  return (
    <div className="absolute inset-0 select-none overflow-hidden rounded-[20px]">
      <Glass
        chroma={0.2}
        className="absolute inset-0"
        depth={12}
        domeDepth={14}
        edgeHighlight={0.3}
        glow={0.12}
        lens={
          <div style={frameStyle}>
            <div data-glass-lens style={triggerLens} />
            {open ? <div data-glass-lens style={popLens} /> : null}
          </div>
        }
        tint={tint}
      >
        <ShowcaseGrid />
      </Glass>

      <div style={frameStyle}>
        <button
          aria-label="More options"
          className="absolute flex cursor-pointer items-center justify-center text-[#1d1d1f] outline-none"
          onClick={() => setOpen((o) => !o)}
          style={{ left: 16, top: 16, width: TRIGGER, height: TRIGGER }}
          type="button"
        >
          <Ellipsis className="size-5" />
        </button>

        {open ? (
          <div
            className="absolute py-2.5"
            style={{ left: POP.left, top: POP.top, width: POP.width }}
          >
            <MenuRow icon={<Pencil />} label="Edit Profile" />
            <MenuRow
              icon={<Share />}
              label="Share Invite Link"
              sublabel="Boost your rate"
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}

export { GlassPopoverDemo };
