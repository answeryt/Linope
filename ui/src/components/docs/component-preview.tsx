import { CodeBlock } from "@/components/docs/code-block";
import { ShowcaseGrid } from "@/components/docs/showcase-grid";
import { cn } from "@/lib/utils";
import { type ReactNode, useState } from "react";

interface ComponentPreviewProps {
  children: ReactNode;
  code: string;
  minHeight?: number;
  onTabChange?: (tab: "preview" | "code") => void;
}

function ComponentPreview({
  children,
  code,
  minHeight = 320,
  onTabChange,
}: ComponentPreviewProps) {
  const [tab, setTab] = useState<"preview" | "code">("preview");
  return (
    <div>
      <div className="flex gap-1 border-border border-b">
        {(["preview", "code"] as const).map((t) => (
          <button
            className={cn(
              "-mb-px cursor-pointer border-b-2 px-3 pb-2 font-medium text-[13.5px] capitalize transition-colors",
              tab === t
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
            key={t}
            onClick={() => {
              setTab(t);
              onTabChange?.(t);
            }}
            type="button"
          >
            {t}
          </button>
        ))}
      </div>
      <div className={cn("mt-4", tab !== "preview" && "hidden")}>
        <div className="preview-pane relative overflow-hidden rounded-[20px] border border-border bg-card">
          <ShowcaseGrid />
          <div
            className="relative flex items-center justify-center px-6 py-10"
            style={{ minHeight }}
          >
            {children}
          </div>
        </div>
      </div>
      <div className={cn("mt-4", tab !== "code" && "hidden")}>
        <CodeBlock code={code} maxHeight={440} />
      </div>
    </div>
  );
}

export { ComponentPreview };
