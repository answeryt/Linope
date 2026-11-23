import type { ReactNode } from "react";
import { DEFAULT_LIQUID_GLASS, GlassDock } from "@/components/ui/glass-dock";

const INK = "#e8eaed";
const SUBTLE = "#8a9099";

const DARK_GLASS = {
  ...DEFAULT_LIQUID_GLASS,
  translucency: { enabled: true, value: 62 },
};

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height={28}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      viewBox="0 0 24 24"
      width={28}
    >
      {children}
    </svg>
  );
}

const ITEMS = [
  {
    id: "home",
    label: "Home",
    icon: <Icon>{<path d="m3 11 9-8 9 8v10h-6v-6H9v6H3V11Z" />}</Icon>,
  },
  {
    id: "dms",
    label: "DMs",
    icon: (
      <Icon>
        <path d="M14 9a2 2 0 0 1-2 2H6l-4 4V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v5Z" />
        <path d="M18 9h2a2 2 0 0 1 2 2v11l-4-4h-6a2 2 0 0 1-2-2v-1" />
      </Icon>
    ),
  },
  {
    id: "activity",
    label: "Activity",
    icon: (
      <Icon>
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.7 21a2 2 0 0 1-3.4 0" />
      </Icon>
    ),
  },
  {
    id: "more",
    label: "More",
    icon: (
      <svg
        aria-hidden="true"
        fill="currentColor"
        height={28}
        viewBox="0 0 24 24"
        width={28}
      >
        <circle cx="5" cy="12" r="2" />
        <circle cx="12" cy="12" r="2" />
        <circle cx="19" cy="12" r="2" />
      </svg>
    ),
  },
];

function StatusBar() {
  return (
    <div
      className="flex items-center justify-between px-7 pt-3 pb-1"
      style={{ color: INK }}
    >
      <span className="font-semibold text-[15px] tracking-tight">9:41</span>
      <div className="flex items-center gap-1.5">
        <svg fill="currentColor" height={11} viewBox="0 0 18 12" width={17}>
          <rect height="4" rx="1" width="3" x="0" y="8" />
          <rect height="6" rx="1" width="3" x="5" y="6" />
          <rect height="8" rx="1" width="3" x="10" y="4" />
          <rect height="10" rx="1" width="3" x="15" y="2" />
        </svg>
        <svg fill="none" height={12} viewBox="0 0 18 13" width={17}>
          <path
            d="M9 11.5a1.4 1.4 0 1 0 0-2.8 1.4 1.4 0 0 0 0 2.8Z"
            fill="currentColor"
          />
          <path
            d="M3.2 6.4a8 8 0 0 1 11.6 0M5.6 8.6a4.7 4.7 0 0 1 6.8 0"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth={1.7}
          />
        </svg>
        <svg fill="none" height={12} viewBox="0 0 26 12" width={25}>
          <rect
            height="11"
            opacity="0.4"
            rx="3"
            stroke="currentColor"
            width="22"
            x="0.5"
            y="0.5"
          />
          <rect fill="currentColor" height="7.5" rx="1.5" width="17" x="2" y="2.2" />
          <rect
            fill="currentColor"
            height="4"
            opacity="0.5"
            rx="1"
            width="1.6"
            x="23.5"
            y="4"
          />
        </svg>
      </div>
    </div>
  );
}

function Header() {
  return (
    <div className="flex items-center justify-between pt-3">
      <button
        className="grid size-[44px] place-items-center rounded-full"
        style={{ background: "#23262d", color: INK }}
        type="button"
      >
        <svg
          fill="none"
          height={22}
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.9}
          viewBox="0 0 24 24"
          width={22}
        >
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M19 8v6M22 11h-6" />
        </svg>
      </button>
      <span className="font-semibold text-[15px]" style={{ color: SUBTLE }}>
        Workspace
      </span>
      <div className="size-[44px]" />
    </div>
  );
}

function Teammate({
  color,
  initials,
  name,
  handle,
  added,
}: {
  color: string;
  initials: string;
  name: string;
  handle: string;
  added?: boolean;
}) {
  return (
    <div className="flex items-center gap-3.5 py-3">
      <div
        className="grid size-[46px] flex-shrink-0 place-items-center rounded-[14px] font-bold text-[15px] text-white"
        style={{ background: color }}
      >
        {initials}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate font-semibold text-[16px]" style={{ color: INK }}>
          {name}
        </div>
        <div className="truncate text-[13px]" style={{ color: SUBTLE }}>
          {handle}
        </div>
      </div>
      <div
        className="rounded-full px-4 py-1.5 font-semibold text-[13px]"
        style={
          added
            ? { background: "#23262d", color: SUBTLE }
            : { background: "#1264a3", color: "#ffffff" }
        }
      >
        {added ? "Added" : "Add"}
      </div>
    </div>
  );
}

function SlackScreen() {
  return (
    <div
      className="pointer-events-auto absolute inset-0 overflow-y-auto [&::-webkit-scrollbar]:hidden"
      style={{ background: "#15171c", scrollbarWidth: "none" }}
    >
      <StatusBar />
      <div className="px-7">
        <Header />
        <h1
          className="mt-7 font-extrabold text-[34px] leading-tight"
          style={{ color: INK }}
        >
          Add Teammates
        </h1>
        <p className="mt-2 text-[15px] leading-snug" style={{ color: SUBTLE }}>
          Slack is better with the people you work with. Invite a few to get
          started.
        </p>
        <div className="mt-6">
          <Teammate
            color="#9b51e0"
            handle="@maya"
            initials="MR"
            name="Maya Romero"
          />
          <Teammate
            added
            color="#2d9d78"
            handle="@dev"
            initials="DK"
            name="Devon Kim"
          />
          <Teammate
            color="#e0518a"
            handle="@priya"
            initials="PN"
            name="Priya Nair"
          />
          <Teammate
            color="#e08a2d"
            handle="@lucas"
            initials="LH"
            name="Lucas Haddad"
          />
          <Teammate
            color="#3b82c4"
            handle="@sam"
            initials="SO"
            name="Sam Okafor"
          />
          <Teammate
            color="#7b8794"
            handle="@noor"
            initials="NA"
            name="Noor Abadi"
          />
        </div>
        <h2
          className="mt-8 font-bold text-[15px] uppercase tracking-wide"
          style={{ color: SUBTLE }}
        >
          Suggested for you
        </h2>
        <div className="mt-2">
          <Teammate
            color="#d4452e"
            handle="@aiko"
            initials="AT"
            name="Aiko Tanaka"
          />
          <Teammate
            color="#1f9e8f"
            handle="@mateo"
            initials="MC"
            name="Mateo Cruz"
          />
          <Teammate
            added
            color="#c0843a"
            handle="@hannah"
            initials="HB"
            name="Hannah Berg"
          />
          <Teammate
            color="#5e6ad2"
            handle="@omar"
            initials="OF"
            name="Omar Farouk"
          />
          <Teammate
            color="#b5479a"
            handle="@zoe"
            initials="ZM"
            name="Zoe Mitchell"
          />
          <Teammate
            color="#2f8f4e"
            handle="@ravi"
            initials="RS"
            name="Ravi Shah"
          />
          <Teammate
            color="#3b82c4"
            handle="@elena"
            initials="EV"
            name="Elena Volkov"
          />
          <Teammate
            color="#9b51e0"
            handle="@kofi"
            initials="KA"
            name="Kofi Asante"
          />
        </div>
        <div className="h-[140px]" />
      </div>
    </div>
  );
}

function GlassDockDarkDemo() {
  return (
    <div className="flex w-full justify-center">
      <GlassDock
        accentColor="#5eb1f7"
        align="bottom"
        className="h-[760px] w-full max-w-[440px] rounded-[44px] shadow-[0_30px_70px_-25px_rgba(0,0,0,0.8)] ring-1 ring-white/10"
        defaultValue="dms"
        glass={DARK_GLASS}
        hoverColor="#ffffff"
        idleColor="#cdd2d8"
        items={ITEMS}
        pillColor="rgba(255,255,255,0.16)"
        tintBlur={16}
        tintColor="34,37,43"
      >
        <SlackScreen />
      </GlassDock>
    </div>
  );
}

export { GlassDockDarkDemo };
