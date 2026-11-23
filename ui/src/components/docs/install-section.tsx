import { useState } from "react";
import { Link } from "@/app/router";
import { CodeBlock } from "@/components/docs/code-block";
import {
  InstallTabs,
  installCommandFor,
  usePm,
} from "@/components/docs/install-tabs";
import { registryEntry } from "@/docs/registry-source";
import { cn } from "@/lib/utils";

const TABS = [
  ["cli", "CLI"],
  ["manual", "Manual"],
] as const;

type Tab = (typeof TABS)[number][0];

function ManualSteps({ name }: { name: string }) {
  const pm = usePm();
  const entry = registryEntry(name);

  if (!entry) {
    return null;
  }

  return (
    <div className="flex flex-col gap-5">
      {entry.registryDependencies.length ? (
        <p className="text-[14px] text-muted-foreground leading-relaxed">
          Built on the Glass engine. Add the{" "}
          <Link
            className="text-foreground underline underline-offset-2"
            to="/docs/components/glass"
          >
            Glass
          </Link>{" "}
          component first.
        </p>
      ) : null}

      {entry.dependencies.length ? (
        <div>
          <p className="mb-2 text-[14px] text-muted-foreground leading-relaxed">
            Install the following dependencies:
          </p>
          <CodeBlock
            code={installCommandFor(pm, entry.dependencies)}
            lang="bash"
          />
        </div>
      ) : null}

      <div>
        <p className="mb-2 text-[14px] text-muted-foreground leading-relaxed">
          Copy and paste the following code into your project.
        </p>
        <div className="flex flex-col gap-4">
          {entry.files.map((file) => (
            <div key={file.name}>
              <div className="mb-1.5 font-mono text-[12.5px] text-muted-foreground">
                {file.name}
              </div>
              <CodeBlock code={file.source} maxHeight={440} />
            </div>
          ))}
        </div>
      </div>

      <p className="text-[14px] text-muted-foreground leading-relaxed">
        Update the import paths to match your project setup.
      </p>
    </div>
  );
}

function InstallSection({ name }: { name: string }) {
  const [tab, setTab] = useState<Tab>("cli");

  return (
    <div>
      <div className="mb-4 flex gap-1 border-border border-b">
        {TABS.map(([value, label]) => (
          <button
            className={cn(
              "-mb-px cursor-pointer border-b-2 px-3 pb-2 font-medium text-[13.5px] transition-colors",
              tab === value
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
            key={value}
            onClick={() => setTab(value)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "cli" ? <InstallTabs name={name} /> : <ManualSteps name={name} />}
    </div>
  );
}

export { InstallSection };
