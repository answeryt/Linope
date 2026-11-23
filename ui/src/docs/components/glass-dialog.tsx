import { GlassDialogDemo } from "@/docs/demos/glass-dialog-demo";
import glassDialogDemoSource from "@/docs/demos/glass-dialog-demo.tsx?raw";
import type { ComponentDoc } from "@/docs/types";

const glassDialogDoc: ComponentDoc = {
  slug: "glass-dialog",
  title: "Dialog",
  description:
    "A modal alert sheet on a glass panel. The page dims behind a blurred scrim and the frosted panel scales into place, like an iOS alert. Built on Base UI Dialog, so focus trapping, escape, and outside-press dismissal are handled.",
  registryName: "glass-dialog",
  demo: GlassDialogDemo,
  demoSource: glassDialogDemoSource,
  props: [
    {
      title: "GlassDialog",
      rows: [
        {
          name: "open / defaultOpen",
          type: "boolean",
          defaultValue: "false",
          description: "Controlled and uncontrolled open state.",
        },
        {
          name: "onOpenChange",
          type: "(open: boolean) => void",
          defaultValue: "undefined",
          description: "Called when the open state changes.",
        },
      ],
    },
    {
      title: "GlassDialogContent",
      rows: [
        {
          name: "tint",
          type: "number",
          defaultValue: "0.75",
          description:
            "Glass tint of the panel. Dialogs default high for legibility over arbitrary pages.",
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

export { glassDialogDoc };
