import { GlassSwitchDemo } from "@/docs/demos/glass-switch-demo";
import glassSwitchDemoSource from "@/docs/demos/glass-switch-demo.tsx?raw";
import type { ComponentDoc } from "@/docs/types";

const glassSwitchDoc: ComponentDoc = {
  slug: "glass-switch",
  title: "Switch",
  description:
    "The iOS toggle. The thumb rests as an opaque platter and lifts into a clear warping lens on press, deforms with drag velocity like gel, and rubber-bands when dragged past the ends. Holding it keeps the lens raised until you let go.",
  registryName: "glass-switch",
  demo: GlassSwitchDemo,
  demoSource: glassSwitchDemoSource,
  tintable: false,
  tintNote:
    "The switch has no tint prop. Its thumb is a solid platter at rest in every appearance mode, exactly like the iOS toggle, and only clears into a lens while pressed.",
  props: [
    {
      title: "GlassSwitch",
      rows: [
        {
          name: "checked / defaultChecked",
          type: "boolean",
          defaultValue: "false",
          description: "Controlled and uncontrolled state.",
        },
        {
          name: "onCheckedChange",
          type: "(checked: boolean) => void",
          defaultValue: "undefined",
          description: "Called when the state commits.",
        },
        {
          name: "disabled",
          type: "boolean",
          defaultValue: "false",
          description: "Disables interaction.",
        },
        {
          name: "name / value",
          type: "string",
          defaultValue: "undefined",
          description: "Form integration for the hidden checkbox.",
        },
        {
          name: "ariaLabel",
          type: "string",
          defaultValue: "undefined",
          description: "Accessible label for the hidden checkbox.",
        },
      ],
    },
  ],
};

export { glassSwitchDoc };
