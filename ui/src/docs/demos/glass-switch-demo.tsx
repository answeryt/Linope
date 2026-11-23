import { ShowcaseCard } from "@/components/docs/showcase-card";
import { GlassSwitch } from "@/components/ui/glass-switch";

function GlassSwitchDemo() {
  return (
    <ShowcaseCard>
      <GlassSwitch ariaLabel="Enable" defaultChecked />
    </ShowcaseCard>
  );
}

export { GlassSwitchDemo };
