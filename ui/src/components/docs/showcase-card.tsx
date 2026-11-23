import type { ReactNode } from "react";

function ShowcaseCard({ children }: { children: ReactNode }) {
  return (
    <div className="inline-flex items-center justify-center rounded-[34px] bg-white px-12 py-10 shadow-[0_22px_60px_-26px_rgba(60,55,120,0.45)]">
      {children}
    </div>
  );
}

export { ShowcaseCard };
