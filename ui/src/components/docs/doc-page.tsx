import type { ReactNode } from "react";

function DocPage({
  title,
  description,
  children,
}: {
  children: ReactNode;
  description: string;
  title: string;
}) {
  return (
    <article className="w-full min-w-0 pb-20">
      <h1 className="font-semibold text-[30px] text-foreground tracking-tight">
        {title}
      </h1>
      <p className="mt-2 max-w-2xl text-[15px] text-muted-foreground leading-relaxed">
        {description}
      </p>
      {children}
    </article>
  );
}

function DocSection({
  id,
  title,
  children,
}: {
  children: ReactNode;
  id: string;
  title: string;
}) {
  return (
    <section className="mt-10">
      <h2
        className="scroll-mt-20 font-semibold text-[20px] text-foreground tracking-tight"
        id={id}
      >
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function DocProse({ children }: { children: ReactNode }) {
  return (
    <p className="mt-3 max-w-2xl text-[14.5px] text-foreground/80 leading-[1.75]">
      {children}
    </p>
  );
}

export { DocPage, DocProse, DocSection };
