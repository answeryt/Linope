import { GlassSliderDemo } from "@/docs/demos/glass-slider-demo";
import glassSliderDemoSource from "@/docs/demos/glass-slider-demo.tsx?raw";
import type { ComponentDoc } from "@/docs/types";

const glassSliderDoc: ComponentDoc = {
  slug: "glass-slider",
  title: "Slider",
  description:
    "An iOS slider whose handle rests as a solid platter and lifts into a clear refracting lens while you drag, keeping the fill value readable through the glass. Overdragging rubber-bands past the ends, and a hidden native range input keeps it accessible.",
  registryName: "glass-slider",
  demo: GlassSliderDemo,
  demoSource: glassSliderDemoSource,
  tintable: false,
  tintNote:
    "The slider has no tint prop. Its handle is a solid platter at rest in every appearance mode, exactly like the iOS slider, and only clears into a lens while dragging.",
  props: [
    {
      title: "GlassSlider",
      rows: [
        {
          name: "value / defaultValue",
          type: "number",
          defaultValue: "50",
          description: "Controlled and uncontrolled value.",
        },
        {
          name: "min / max",
          type: "number",
          defaultValue: "0 / 100",
          description: "Value range.",
        },
        {
          name: "step",
          type: "number",
          defaultValue: "1",
          description: "Snap increment.",
        },
        {
          name: "onValueChange",
          type: "(value: number) => void",
          defaultValue: "undefined",
          description: "Called with the snapped value while dragging.",
        },
        {
          name: "disabled",
          type: "boolean",
          defaultValue: "false",
          description: "Disables interaction.",
        },
        {
          name: "ariaLabel",
          type: "string",
          defaultValue: '"Value"',
          description: "Accessible label for the hidden range input.",
        },
      ],
    },
  ],
};

export { glassSliderDoc };
