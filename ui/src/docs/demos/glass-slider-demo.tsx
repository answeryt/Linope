import { ShowcaseCard } from "@/components/docs/showcase-card";
import { GlassSlider } from "@/components/ui/glass-slider";

function GlassSliderDemo() {
  return (
    <ShowcaseCard>
      <GlassSlider ariaLabel="Volume" defaultValue={38} />
    </ShowcaseCard>
  );
}

export { GlassSliderDemo };
