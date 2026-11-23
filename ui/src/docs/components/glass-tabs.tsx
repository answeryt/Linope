import { GlassTabsDemo } from "@/docs/demos/glass-tabs-demo";
import glassTabsDemoSource from "@/docs/demos/glass-tabs-demo.tsx?raw";
import type { ComponentDoc } from "@/docs/types";

const glassTabsDoc: ComponentDoc = {
  slug: "glass-tabs",
  title: "Tabs",
  description:
    "Base UI tabs where the selection indicator is a glass lens. It springs between options, stretching like a droplet with velocity, and sits behind the crisp labels so they stay perfectly legible while it slides.",
  registryName: "glass-tabs",
  demo: GlassTabsDemo,
  demoSource: glassTabsDemoSource,
  props: [
    {
      title: "Tabs",
      rows: [
        {
          name: "value / defaultValue",
          type: "string",
          defaultValue: "undefined",
          description: "Controlled and uncontrolled selected tab.",
        },
        {
          name: "onValueChange",
          type: "(value) => void",
          defaultValue: "undefined",
          description: "Called when the selection changes.",
        },
      ],
    },
    {
      title: "TabsList",
      rows: [
        {
          name: "tint",
          type: "number",
          defaultValue: "0",
          description:
            "Glass tint of the selection lens from 0 (clear) to 1 (opaque).",
        },
      ],
    },
    {
      title: "TabsTrigger",
      rows: [
        {
          name: "value",
          type: "string",
          defaultValue: "required",
          description: "Tab identifier this trigger selects.",
        },
      ],
    },
  ],
};

export { glassTabsDoc };
