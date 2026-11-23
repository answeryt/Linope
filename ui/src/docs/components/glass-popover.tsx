import { GlassPopoverDemo } from "@/docs/demos/glass-popover-demo";
import glassPopoverDemoSource from "@/docs/demos/glass-popover-demo.tsx?raw";
import type { ComponentDoc } from "@/docs/types";

const glassPopoverDoc: ComponentDoc = {
  slug: "glass-popover",
  title: "Popover",
  description:
    "The iOS context menu: a frosted glass panel attached to its trigger, blurring whatever sits behind it, with icon, label, and sublabel rows. Built on Base UI Menu, so arrow keys, typeahead, and close-on-select work out of the box.",
  registryName: "glass-popover",
  demo: GlassPopoverDemo,
  demoSource: glassPopoverDemoSource,
  demoMinHeight: 380,
  props: [
    {
      title: "GlassPopoverContent",
      rows: [
        {
          name: "side",
          type: '"top" | "right" | "bottom" | "left"',
          defaultValue: '"bottom"',
          description: "Which side of the trigger the panel opens on.",
        },
        {
          name: "align",
          type: '"start" | "center" | "end"',
          defaultValue: '"start"',
          description: "Alignment against the trigger.",
        },
        {
          name: "sideOffset",
          type: "number",
          defaultValue: "10",
          description: "Gap between trigger and panel in px.",
        },
        {
          name: "tint",
          type: "number",
          defaultValue: "0.55",
          description: "Glass tint of the panel from 0 (clear) to 1 (opaque).",
        },
        {
          name: "tintColor",
          type: "string",
          defaultValue: "theme",
          description: "Tint color as an r,g,b triple.",
        },
      ],
    },
    {
      title: "GlassPopoverItem",
      rows: [
        {
          name: "label",
          type: "string",
          defaultValue: "required",
          description: "Row label, also used for keyboard typeahead.",
        },
        {
          name: "sublabel",
          type: "string",
          defaultValue: "undefined",
          description: "Smaller secondary line under the label.",
        },
        {
          name: "icon",
          type: "ReactNode",
          defaultValue: "undefined",
          description: "Leading icon slot.",
        },
        {
          name: "destructive",
          type: "boolean",
          defaultValue: "false",
          description: "Tints the row red for destructive actions.",
        },
        {
          name: "onClick",
          type: "(event) => void",
          defaultValue: "undefined",
          description: "Action handler. The menu closes on click by default.",
        },
      ],
    },
  ],
};

export { glassPopoverDoc };
