import { GlassInputDemo } from "@/docs/demos/glass-input-demo";
import glassInputDemoSource from "@/docs/demos/glass-input-demo.tsx?raw";
import type { ComponentDoc } from "@/docs/types";

const glassInputDoc: ComponentDoc = {
  slug: "glass-input",
  title: "Input",
  description:
    "An iOS search bar: a text field inside a frosted glass capsule with a leading icon slot. Focusing glows in a soft ring while the tint lifts slightly, so the field reads as raised glass while you type.",
  registryName: "glass-input",
  demo: GlassInputDemo,
  demoSource: glassInputDemoSource,
  props: [
    {
      title: "GlassInput",
      rows: [
        {
          name: "height",
          type: "number",
          defaultValue: "44",
          description: "Capsule height in px. The radius is always height / 2.",
        },
        {
          name: "icon",
          type: "ReactNode",
          defaultValue: "undefined",
          description: "Leading icon slot.",
        },
        {
          name: "tint",
          type: "number",
          defaultValue: "0.5",
          description: "Glass tint of the capsule from 0 (clear) to 1 (opaque).",
        },
        {
          name: "tintColor",
          type: "string",
          defaultValue: "theme",
          description: "Tint color as an r,g,b triple.",
        },
        {
          name: "inputClassName",
          type: "string",
          defaultValue: "undefined",
          description:
            "Classes for the inner input element. className styles the capsule.",
        },
        {
          name: "onValueChange",
          type: "(value: string) => void",
          defaultValue: "undefined",
          description:
            "Convenience change callback from Base UI Input, alongside the native onChange.",
        },
        {
          name: "...props",
          type: "Input.Props",
          defaultValue: "",
          description: "All native input props are forwarded.",
        },
      ],
    },
  ],
};

export { glassInputDoc };
