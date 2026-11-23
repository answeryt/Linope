import { CopyButton } from "@/components/docs/copy-button";
import { REGISTRY_BASE } from "@/docs/nav";
import { cn } from "@/lib/utils";
import { useSyncExternalStore } from "react";

const PMS = ["pnpm", "npm", "yarn", "bun"] as const;
type Pm = (typeof PMS)[number];

const STORAGE_KEY = "lore-glass:pm";
const listeners = new Set<() => void>();

let currentPm: Pm = (() => {
  const raw =
    typeof localStorage === "undefined" ? null : localStorage.getItem(STORAGE_KEY);
  return PMS.includes(raw as Pm) ? (raw as Pm) : "bun";
})();

function setPm(pm: Pm) {
  currentPm = pm;
  localStorage.setItem(STORAGE_KEY, pm);
  for (const fn of listeners) {
    fn();
  }
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function usePm(): Pm {
  return useSyncExternalStore(subscribe, () => currentPm);
}

function commandFor(pm: Pm, target: string): string {
  switch (pm) {
    case "pnpm":
      return `pnpm dlx shadcn@latest add ${target}`;
    case "npm":
      return `npx shadcn@latest add ${target}`;
    case "yarn":
      return `yarn dlx shadcn@latest add ${target}`;
    case "bun":
      return `bunx shadcn@latest add ${target}`;
  }
}

function installCommandFor(pm: Pm, deps: string[]): string {
  const packages = deps.join(" ");
  switch (pm) {
    case "pnpm":
      return `pnpm add ${packages}`;
    case "npm":
      return `npm install ${packages}`;
    case "yarn":
      return `yarn add ${packages}`;
    case "bun":
      return `bun add ${packages}`;
  }
}

function PmCommand({ build }: { build: (pm: Pm) => string }) {
  const pm = usePm();
  const command = build(pm);
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-[var(--code-bg)]">
      <div className="flex items-center justify-between border-border border-b px-2 pt-1">
        <div className="flex">
          {PMS.map((p) => (
            <button
              className={cn(
                "cursor-pointer border-b-2 px-2.5 pb-1.5 font-medium text-[12.5px] transition-colors",
                pm === p
                  ? "border-foreground text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
              key={p}
              onClick={() => setPm(p)}
              type="button"
            >
              {p}
            </button>
          ))}
        </div>
        <CopyButton className="mb-1" text={command} />
      </div>
      <pre className="overflow-x-auto px-4 py-3.5 font-mono text-[12.5px] text-foreground/85 leading-relaxed">
        <code>{command}</code>
      </pre>
    </div>
  );
}

function InstallTabs({ name }: { name: string }) {
  return <PmCommand build={(pm) => commandFor(pm, `${REGISTRY_BASE}/${name}.json`)} />;
}

export { InstallTabs, installCommandFor, usePm };
