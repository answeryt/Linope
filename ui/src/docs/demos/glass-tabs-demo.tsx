import { Chart, Gear, Grid, House } from "@/components/docs/icons";
import { ShowcaseCard } from "@/components/docs/showcase-card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/glass-tabs";

const ITEMS = [
  { value: "home", label: "Home", Icon: House },
  { value: "library", label: "Library", Icon: Grid },
  { value: "stats", label: "Stats", Icon: Chart },
  { value: "settings", label: "Settings", Icon: Gear },
];

function GlassTabsDemo({ tint }: { tint?: number }) {
  return (
    <ShowcaseCard>
      <Tabs defaultValue="home">
        <TabsList tint={tint}>
          {ITEMS.map(({ value, label, Icon }) => (
            <TabsTrigger key={value} value={value}>
              <Icon className="size-[18px]" />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </ShowcaseCard>
  );
}

export { GlassTabsDemo };
