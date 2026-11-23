import { Search } from "@/components/docs/icons";
import { GlassInput } from "@/components/ui/glass-input";

function GlassInputDemo({ tint }: { tint?: number }) {
  return (
    <GlassInput
      className="w-72"
      icon={<Search />}
      placeholder="Search components"
      tint={tint}
    />
  );
}

export { GlassInputDemo };
