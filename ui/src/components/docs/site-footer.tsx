import { Github } from "@/components/docs/icons";

const REPO_URL = "https://github.com/Simonstorms/lore-glass";

function SiteFooter() {
  return (
    <footer className="mt-24 flex flex-col items-center gap-3 border-border/60 border-t pt-12 pb-2 text-center">
      <a
        className="glass-chip group inline-flex items-center gap-2.5 rounded-full py-1.5 pr-4 pl-1.5 font-medium text-[13.5px] text-foreground transition-transform duration-200 hover:-translate-y-0.5"
        href={REPO_URL}
        rel="noreferrer noopener"
        target="_blank"
      >
        <span className="glass-lens flex size-7 items-center justify-center rounded-full">
          <Github className="size-[15px]" />
        </span>
        Star on GitHub
        <span
          aria-hidden="true"
          className="text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5"
        >
          →
        </span>
      </a>
      <p className="text-[12.5px] text-muted-foreground">
        Simonstorms/lore-glass · MIT
      </p>
      <p className="max-w-sm text-[12.5px] text-muted-foreground leading-relaxed">
        The glass technique is built on the amazing work of the team at{" "}
        <a
          className="font-medium text-foreground/80 underline underline-offset-2 transition-colors hover:text-foreground"
          href="https://aave.com/design/building-glass-for-the-web"
          rel="noreferrer noopener"
          target="_blank"
        >
          Aave Labs, Building Glass for the Web
        </a>
        . Thank you.
      </p>
    </footer>
  );
}

export { SiteFooter };
