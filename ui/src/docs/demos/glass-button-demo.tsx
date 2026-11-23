import { Bell, Ellipsis } from "@/components/docs/icons";
import { GlassButton } from "@/components/ui/glass-button";

function GlassButtonDemo({ tint }: { tint?: number }) {
  return (
    <div className="flex items-center justify-center gap-5">
      <GlassButton aria-label="More options" tint={tint}>
        <Ellipsis className="size-5" />
      </GlassButton>
      <GlassButton aria-label="Notifications" tint={tint}>
        <Bell className="size-5" />
      </GlassButton>
      <GlassButton tint={tint} variant="capsule">
        Continue
      </GlassButton>
    </div>
  );
}

export { GlassButtonDemo };
