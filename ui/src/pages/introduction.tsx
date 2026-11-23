import { Link, navigate } from "@/app/router";
import chrome from "@/assets/chrome.jpg";
import glassWave from "@/assets/glass-wave.jpg";
import irisPrism from "@/assets/iris-prism.jpg";
import irisRainbow from "@/assets/iris-rainbow.jpg";
import { Bell, Chart, Ellipsis, Grid, House } from "@/components/docs/icons";
import { GlassBubble } from "@/components/glass-bubble";
import { isSafariBrowser } from "@/components/ui/glass";
import { GlassButton } from "@/components/ui/glass-button";
import { GlassSwitch } from "@/components/ui/glass-switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/glass-tabs";
import { type PointerEvent, type ReactNode, useRef, useState } from "react";

const TAB_ITEMS = [
  { value: "home", label: "Home", Icon: House },
  { value: "library", label: "Library", Icon: Grid },
  { value: "stats", label: "Stats", Icon: Chart },
];

function Tile({
  image,
  to,
  label,
  darkLabel = false,
  children,
}: {
  children: ReactNode;
  darkLabel?: boolean;
  image: string;
  label?: string;
  to?: string;
}) {
  return (
    <div className="group relative flex h-[212px] overflow-hidden rounded-[20px] border border-border/50">
      <img
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
        draggable={false}
        src={image}
      />
      <div
        aria-hidden="true"
        className={
          darkLabel
            ? "absolute inset-0 bg-gradient-to-t from-white/80 via-white/15 to-transparent"
            : "absolute inset-0 bg-gradient-to-t from-black/35 via-transparent to-black/5"
        }
      />
      <div
        className={`relative flex w-full items-center justify-center px-5 ${label ? "pb-8" : ""}`}
      >
        {children}
      </div>
      {label && to ? (
        <Link
          className={
            darkLabel
              ? "absolute bottom-3 left-4 inline-flex items-center gap-1 font-medium text-[12.5px] text-foreground transition-colors hover:text-foreground/70"
              : "absolute bottom-3 left-4 inline-flex items-center gap-1 font-medium text-[12.5px] text-white/90 drop-shadow-[0_1px_6px_rgba(0,0,0,0.55)] transition-colors hover:text-white"
          }
          to={to}
        >
          {label}
          <span aria-hidden="true">→</span>
        </Link>
      ) : null}
    </div>
  );
}

const HERO_CONTENT_CLASS =
  "flex min-h-[480px] flex-col justify-between gap-10 p-7 sm:p-10";

function LoreGlassHero() {
  const lensRef = useRef<HTMLDivElement | null>(null);
  const [active, setActive] = useState(false);
  const [showBubble] = useState(() => !isSafariBrowser());

  const media = (
    <>
      <img
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-cover"
        draggable={false}
        src={glassWave}
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/15 to-black/35"
      />
    </>
  );

  const body = (
    <div>
      <h1 className="font-display font-bold text-[46px] text-white leading-[0.95] tracking-tight drop-shadow-[0_2px_20px_rgba(0,0,0,0.45)] sm:text-[68px]">
        lore-glass
      </h1>
      <p className="mt-4 max-w-md text-[15px] text-white/85 leading-relaxed drop-shadow-[0_1px_10px_rgba(0,0,0,0.5)]">
        Apple's Liquid Glass for the web. A cross-browser displacement-map lens,
        installable with the shadcn CLI.
      </p>
      <div className="mt-7 flex flex-wrap items-center gap-3">
        <GlassButton
          className="text-white"
          onClick={() => navigate("/docs/installation")}
          tint={0.25}
          variant="capsule"
        >
          Get started
        </GlassButton>
        <GlassButton aria-label="Notifications" className="text-white" tint={0.25}>
          <Bell className="size-5" />
        </GlassButton>
        <GlassButton aria-label="More options" className="text-white" tint={0.25}>
          <Ellipsis className="size-5" />
        </GlassButton>
      </div>
    </div>
  );

  const scene = (
    <>
      {media}
      <div aria-hidden="true" className={`absolute inset-0 ${HERO_CONTENT_CLASS}`} inert>
        {body}
      </div>
    </>
  );

  const handlePointerMove = (event: PointerEvent<HTMLElement>) => {
    const lens = lensRef.current;
    if (!lens) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    lens.style.transform = `translate(calc(${x}px - 50%), calc(${y}px - 50%))`;
    if (!active) {
      setActive(true);
    }
  };

  return (
    <section
      className="relative overflow-hidden rounded-[28px] border border-border/50"
      onPointerLeave={() => setActive(false)}
      onPointerMove={handlePointerMove}
    >
      {media}
      <div className={`relative ${HERO_CONTENT_CLASS}`}>{body}</div>
      {showBubble ? (
        <GlassBubble active={active} background={scene} lensRef={lensRef} />
      ) : null}
    </section>
  );
}

function IntroductionPage() {
  return (
    <article className="w-full min-w-0 pb-24">
      <LoreGlassHero />

      <section className="mt-16">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="font-semibold text-[22px] text-foreground tracking-tight">
            Nine components
          </h2>
          <Link
            className="shrink-0 text-[13.5px] text-muted-foreground transition-colors hover:text-foreground"
            to="/docs/installation"
          >
            See all →
          </Link>
        </div>
        <p className="mt-1.5 max-w-md text-[14px] text-muted-foreground leading-relaxed">
          A look at two. All nine install the same way, with a single shadcn
          command.
        </p>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <Tile darkLabel image={chrome}>
            <div className="inline-flex items-center justify-center rounded-[28px] bg-white px-10 py-7 shadow-[0_18px_50px_-24px_rgba(60,55,120,0.45)]">
              <GlassSwitch ariaLabel="Enable" defaultChecked />
            </div>
          </Tile>
          <Tile image={irisRainbow}>
            <Tabs defaultValue="home">
              <TabsList tint={0.4}>
                {TAB_ITEMS.map(({ value, label, Icon }) => (
                  <TabsTrigger key={value} value={value}>
                    <Icon className="size-[18px]" />
                    {label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </Tile>
          <Link
            className="group relative flex h-[212px] flex-col justify-end overflow-hidden rounded-[20px] border border-border/50 p-6"
            to="/docs/installation"
          >
            <img
              alt=""
              aria-hidden="true"
              className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
              draggable={false}
              src={irisPrism}
            />
            <div
              aria-hidden="true"
              className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/25 to-transparent"
            />
            <div className="relative">
              <div className="font-semibold text-[19px] text-white tracking-tight">
                Install with shadcn
              </div>
              <p className="mt-1 text-[13px] text-white/75">
                Nine components, one command.
              </p>
              <span className="mt-3 inline-flex items-center gap-1 font-medium text-[13px] text-white">
                Browse the registry
                <span aria-hidden="true">→</span>
              </span>
            </div>
          </Link>
        </div>
      </section>
    </article>
  );
}

export { IntroductionPage };
