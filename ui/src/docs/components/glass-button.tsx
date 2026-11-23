import { GlassButtonDemo } from "@/docs/demos/glass-button-demo";
import glassButtonDemoSource from "@/docs/demos/glass-button-demo.tsx?raw";
import type { ComponentDoc } from "@/docs/types";

const glassButtonDoc: ComponentDoc = {
  slug: "glass-button",
  title: "Button",
  description:
    "The circular iOS icon button and its text capsule sibling. A frosted glass disc blurs whatever sits behind it, and pressing squeezes the button with a gel response: the disc scales down and the tint clears while held.",
  registryName: "glass-button",
  demo: GlassButtonDemo,
  demoSource: glassButtonDemoSource,
  props: [
    {
      title: "GlassButton",
      rows: [
        {
          name: "variant",
          type: '"icon" | "capsule"',
          defaultValue: '"icon"',
          description:
            "icon renders a fixed-size disc, capsule a pill that grows with its label.",
        },
        {
          name: "size",
          type: "number",
          defaultValue: "44",
          description: "Disc diameter, or capsule height, in px.",
        },
        {
          name: "tint",
          type: "number",
          defaultValue: "0.2",
          description: "Glass tint from 0 (clear) to 1 (opaque).",
        },
        {
          name: "tintColor",
          type: "string",
          defaultValue: "theme",
          description: "Tint color as an r,g,b triple.",
        },
        {
          name: "...props",
          type: 'ComponentProps<"button">',
          defaultValue: "",
          description: "All native button props are forwarded.",
        },
      ],
    },
  ],
};

export { glassButtonDoc };
