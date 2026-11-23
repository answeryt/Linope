import { CopyButton } from "@/components/docs/copy-button";
import { highlight, type Lang } from "@/docs/highlight";
import { cn } from "@/lib/utils";
import { Suspense, use } from "react";

function Highlighted({ code, lang }: { code: string; lang: Lang }) {
  const html = use(highlight(code, lang));
  return (
    <div
      className="shiki-block overflow-x-auto"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

interface CodeBlockProps {
  className?: string;
  code: string;
  lang?: Lang;
  maxHeight?: number;
}

function CodeBlock({ code, lang = "tsx", className, maxHeight }: CodeBlockProps) {
  const trimmed = code.trimEnd();
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-border bg-[var(--code-bg)]",
        className
      )}
    >
      <CopyButton className="absolute top-2.5 right-2.5 z-10" text={trimmed} />
      <div className="overflow-y-auto" style={maxHeight ? { maxHeight } : undefined}>
        <Suspense
          fallback={
            <pre className="overflow-x-auto px-4 py-3.5 font-mono text-[13px] leading-[1.7]">
              <code>{trimmed}</code>
            </pre>
          }
        >
          <Highlighted code={trimmed} lang={lang} />
        </Suspense>
      </div>
    </div>
  );
}

export { CodeBlock };
