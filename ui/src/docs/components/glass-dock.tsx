import { GlassDockDarkDemo } from "@/docs/demos/glass-dock-dark-demo";
import glassDockDarkDemoSource from "@/docs/demos/glass-dock-dark-demo.tsx?raw";
import { GlassDockDemo } from "@/docs/demos/glass-dock-demo";
import glassDockDemoSource from "@/docs/demos/glass-dock-demo.tsx?raw";
import type { ComponentDoc } from "@/docs/types";

const glassDockDoc: ComponentDoc = {
  slug: "glass-dock",
  title: "Dock",
  description:
    "A macOS-style liquid-glass application dock: an always-glass bar that refracts the content behind it, with crisp icons on top. The selected item rests as a soft grey pill; tap another item or grab and drag the pill and it lifts into a glass lens that refracts and magnifies each icon and label it travels over, then settles back into a pill (grey to glass to grey). The selection glass blends seamlessly into the bar, no rectangular box.",
  registryName: "glass-dock",
  demo: GlassDockDemo,
  demoSource: glassDockDemoSource,
  tintable: false,
  tintNote:
    "The dock manages its own liquid-glass material through the glass prop and a fixed bar tint, so the page-wide tint slider does not apply here.",
  props: [
    {
      title: "GlassDock",
      rows: [
        {
          name: "items",
          type: "{ id, label, icon, badge? }[]",
          defaultValue: "required",
          description:
            "Dock entries. Each has an id, a label, a stroked icon node, and an optional badge.",
        },
        {
          name: "value / defaultValue",
          type: "string",
          defaultValue: "first item",
          description: "Controlled and uncontrolled selected item id.",
        },
        {
          name: "onValueChange",
          type: "(id) => void",
          defaultValue: "undefined",
          description: "Called when the selected item changes.",
        },
        {
          name: "glass",
          type: "LiquidGlassConfig",
          defaultValue: "DEFAULT_LIQUID_GLASS",
          description:
            "Tunes the material: specular, blur, refraction { amount, thickness }, translucency, shadow.",
        },
      ],
    },
  ],
  examples: [
    {
      title: "Dark",
      description:
        "A dark, Slack-style bottom bar. Pass a dark tintColor plus light idle/hover colors and a blue accent; the bar frosts and refracts the dark screen behind it while the selected item rests as a soft lighter pill.",
      component: GlassDockDarkDemo,
      source: glassDockDarkDemoSource,
    },
  ],
};

export { glassDockDoc };
