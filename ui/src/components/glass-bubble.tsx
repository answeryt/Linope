"use client";

import { Glass } from "@/components/ui/glass";
import { cn } from "@/lib/utils";
import type { ReactNode, RefObject } from "react";

function GlassBubble({
  active,
  background,
  lensRef,
  size = 140,
}: {
  active: boolean;
  background: ReactNode;
  lensRef: RefObject<HTMLDivElement | null>;
  size?: number;
}) {
  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-0 transition-opacity duration-300 ease-out",
        active ? "opacity-100" : "opacity-0"
      )}
    >
      <Glass
        chroma={0.3}
        className="absolute inset-0"
        depth={10}
        domeDepth={18}
        edgeHighlight={0.5}
        glow={0.2}
        lens={
          <div
            className="absolute top-0 left-0 rounded-full"
            data-glass-lens
            ref={lensRef}
            style={{ width: size, height: size }}
          />
        }
        reveal
        tint={0}
      >
        <div className="absolute inset-0">{background}</div>
      </Glass>
    </div>
  );
}

export { GlassBubble };
