import { GlassTooltipDemo } from "@/docs/demos/glass-tooltip-demo";
import glassTooltipDemoSource from "@/docs/demos/glass-tooltip-demo.tsx?raw";
import type { ComponentDoc } from "@/docs/types";

const glassTooltipDoc: ComponentDoc = {
  slug: "glass-tooltip",
  title: "Tooltip",
  description:
    "A small frosted glass chip that scales in from its anchor on hover. Wrap a group in GlassTooltipProvider and adjacent tooltips share one delay, so moving between buttons feels instant, the same grouping iOS toolbars use.",
  registryName: "glass-tooltip",
  demo: GlassTooltipDemo,
  demoSource: glassTooltipDemoSource,
  props: [
    {
      title: "GlassTooltipProvider",
      rows: [
        {
          name: "delay",
          type: "number",
          defaultValue: "600",
          description: "Hover delay in ms before the first tooltip opens.",
        },
        {
          name: "closeDelay",
          type: "number",
          defaultValue: "0",
          description: "Delay in ms before a tooltip closes.",
        },
        {
          name: "timeout",
          type: "number",
          defaultValue: "400",
          description:
            "Grace window in ms during which moving to a neighboring trigger opens its tooltip instantly.",
        },
      ],
    },
    {
      title: "GlassTooltipContent",
      rows: [
        {
          name: "side",
          type: '"top" | "right" | "bottom" | "left"',
          defaultValue: '"top"',
          description: "Which side of the trigger the chip appears on.",
        },
        {
          name: "align",
          type: '"start" | "center" | "end"',
          defaultValue: '"center"',
          description: "Alignment against the trigger.",
        },
        {
          name: "sideOffset",
          type: "number",
          defaultValue: "8",
          description: "Gap between trigger and chip in px.",
        },
        {
          name: "tint",
          type: "number",
          defaultValue: "0.6",
          description: "Glass tint of the chip from 0 (clear) to 1 (opaque).",
        },
        {
          name: "tintColor",
          type: "string",
          defaultValue: "theme",
          description: "Tint color as an r,g,b triple.",
        },
      ],
    },
  ],
};

export { glassTooltipDoc };
