import { type CSSProperties, useState } from "react";
import { ShowcaseGrid } from "@/components/docs/showcase-grid";
import { Glass } from "@/components/ui/glass";

const STAGE_W = 440;
const STAGE_H = 300;

const DIALOG = { w: 300, h: 190 };
const DIALOG_X = (STAGE_W - DIALOG.w) / 2;
const DIALOG_Y = (STAGE_H - DIALOG.h) / 2;

const BTN_H = 38;
const RESET = { w: 78, x: DIALOG_X + DIALOG.w - 22 - 78, y: DIALOG_Y + DIALOG.h - 22 - BTN_H };
const CANCEL = { w: 86, x: RESET.x - 10 - 86, y: RESET.y };

const TRIGGER = { w: 150, h: 46 };
const TRIGGER_X = (STAGE_W - TRIGGER.w) / 2;
const TRIGGER_Y = (STAGE_H - TRIGGER.h) / 2;

const frameStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "50%",
  width: STAGE_W,
  height: STAGE_H,
  transform: "translate(-50%, -50%)",
};

const lensShadow =
  "inset 0 1px 1.5px rgba(255,255,255,0.55), 0 16px 38px -14px rgba(0,0,0,0.4)";

function rect(
  x: number,
  y: number,
  w: number,
  h: number,
  radius: number
): CSSProperties {
  return {
    position: "absolute",
    left: x,
    top: y,
    width: w,
    height: h,
    borderRadius: radius,
    boxShadow: lensShadow,
  };
}

function GlassDialogDemo({ tint }: { tint?: number }) {
  const [open, setOpen] = useState(true);

  const lenses = open ? (
    <>
      <div data-glass-lens style={rect(DIALOG_X, DIALOG_Y, DIALOG.w, DIALOG.h, 28)} />
      <div data-glass-lens style={rect(CANCEL.x, CANCEL.y, CANCEL.w, BTN_H, BTN_H / 2)} />
      <div data-glass-lens style={rect(RESET.x, RESET.y, RESET.w, BTN_H, BTN_H / 2)} />
    </>
  ) : (
    <div
      data-glass-lens
      style={rect(TRIGGER_X, TRIGGER_Y, TRIGGER.w, TRIGGER.h, TRIGGER.h / 2)}
    />
  );

  return (
    <div className="absolute inset-0 overflow-hidden rounded-[20px]">
      <Glass
        chroma={0.3}
        className="absolute inset-0"
        depth={11}
        domeDepth={14}
        edgeHighlight={0.3}
        glow={0.12}
        lens={<div style={frameStyle}>{lenses}</div>}
        tint={tint}
      >
        <ShowcaseGrid />
        {open ? (
          <div aria-hidden="true" className="absolute inset-0 bg-black/35" />
        ) : null}
      </Glass>

      <div style={frameStyle}>
        {open ? (
          <>
            <button
              aria-label="Close dialog"
              className="absolute inset-0 cursor-default outline-none"
              onClick={() => setOpen(false)}
              type="button"
            />
            <div
              className="absolute text-[#1d1d1f]"
              style={{ left: DIALOG_X + 24, top: DIALOG_Y + 24, width: DIALOG.w - 48 }}
            >
              <div className="font-semibold text-[17px] leading-snug tracking-tight">
                Reset all settings?
              </div>
              <div className="mt-1.5 text-[14px] leading-relaxed opacity-65">
                This restores every preference to its default value. You cannot
                undo this action.
              </div>
            </div>
            <button
              className="absolute flex cursor-pointer items-center justify-center font-medium text-[#1d1d1f] text-[14px] outline-none"
              onClick={() => setOpen(false)}
              style={{ left: CANCEL.x, top: CANCEL.y, width: CANCEL.w, height: BTN_H }}
              type="button"
            >
              Cancel
            </button>
            <button
              className="absolute flex cursor-pointer items-center justify-center font-medium text-[#e5484d] text-[14px] outline-none"
              onClick={() => setOpen(false)}
              style={{ left: RESET.x, top: RESET.y, width: RESET.w, height: BTN_H }}
              type="button"
            >
              Reset
            </button>
          </>
        ) : (
          <button
            className="absolute flex cursor-pointer items-center justify-center font-medium text-[#1d1d1f] text-[15px] outline-none"
            onClick={() => setOpen(true)}
            style={{
              left: TRIGGER_X,
              top: TRIGGER_Y,
              width: TRIGGER.w,
              height: TRIGGER.h,
            }}
            type="button"
          >
            Show Dialog
          </button>
        )}
      </div>
    </div>
  );
}

export { GlassDialogDemo };
