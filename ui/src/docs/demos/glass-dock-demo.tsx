import type { ReactNode } from "react";
import { DEFAULT_LIQUID_GLASS, GlassDock } from "@/components/ui/glass-dock";

const NAVY = "#0a2c40";
const MUTED = "#5d6e7b";

const DOCK_GLASS = {
  ...DEFAULT_LIQUID_GLASS,
  translucency: { enabled: true, value: 55 },
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
    id: "dashboard",
    label: "Dashboard",
    icon: (
      <Icon>
        <rect height="7" rx="1.5" width="7" x="3" y="3" />
        <rect height="7" rx="1.5" width="7" x="14" y="3" />
        <rect height="7" rx="1.5" width="7" x="3" y="14" />
        <rect height="7" rx="1.5" width="7" x="14" y="14" />
      </Icon>
    ),
  },
  {
    id: "analytics",
    label: "Analytics",
    icon: <Icon>{<path d="M4 20V10M10 20V4M16 20v-7M22 20V7" />}</Icon>,
  },
  {
    id: "settings",
    label: "Settings",
    icon: (
      <Icon>
        <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 0 1-4 0v-.09A1.7 1.7 0 0 0 8.97 19.35a1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 0 1 0-4h.09A1.7 1.7 0 0 0 4.65 8.95a1.7 1.7 0 0 0-.34-1.88l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9.02 4.6 1.7 1.7 0 0 0 10.05 3V3a2 2 0 0 1 4 0v.09A1.7 1.7 0 0 0 15.08 4.65a1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.88 1.7 1.7 0 0 0 1.56 1.03H21a2 2 0 0 1 0 4h-.09A1.7 1.7 0 0 0 19.4 15Z" />
      </Icon>
    ),
  },
];

function StatusBar() {
  return (
    <div
      className="flex items-center justify-between px-7 pt-3 pb-1"
      style={{ color: NAVY }}
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
          <rect fill="currentColor" height="4" opacity="0.5" rx="1" width="1.6" x="23.5" y="4" />
        </svg>
      </div>
    </div>
  );
}

function TopActions() {
  return (
    <div className="flex items-center justify-end gap-3 pt-3">
      <div
        className="flex items-center gap-5 rounded-full bg-white px-5 py-2.5"
        style={{ boxShadow: "0 6px 18px -8px rgba(10,44,64,0.35)", color: NAVY }}
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
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
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
          <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
          <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 0 1-4 0v-.09A1.7 1.7 0 0 0 8.97 19.35a1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 0 1 0-4h.09A1.7 1.7 0 0 0 4.65 8.95a1.7 1.7 0 0 0-.34-1.88l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9.02 4.6 1.7 1.7 0 0 0 10.05 3V3a2 2 0 0 1 4 0v.09A1.7 1.7 0 0 0 15.08 4.65a1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.88 1.7 1.7 0 0 0 1.56 1.03H21a2 2 0 0 1 0 4h-.09A1.7 1.7 0 0 0 19.4 15Z" />
        </svg>
      </div>
      <button
        className="grid size-[52px] place-items-center rounded-full text-white"
        style={{ background: "#2f6bff", boxShadow: "0 8px 20px -6px rgba(47,107,255,0.6)" }}
        type="button"
      >
        <svg
          fill="none"
          height={26}
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth={2.4}
          viewBox="0 0 24 24"
          width={26}
        >
          <path d="M12 5v14M5 12h14" />
        </svg>
      </button>
    </div>
  );
}

function WeeklyGoal() {
  return (
    <div
      className="mt-8 flex items-center gap-4 rounded-[20px] px-5 py-5"
      style={{ background: "#eef3f7" }}
    >
      <svg fill="none" height={42} viewBox="0 0 42 42" width={42}>
        <circle cx="21" cy="21" r="16" stroke="#c0d4f2" strokeWidth="5" />
        <circle
          cx="21"
          cy="21"
          r="16"
          stroke="#3b7bff"
          strokeDasharray="100.5"
          strokeDashoffset="67"
          strokeLinecap="round"
          strokeWidth="5"
          transform="rotate(-90 21 21)"
        />
        <path d="M19 15.5 26 21l-7 5.5V15.5Z" fill="#3b7bff" />
      </svg>
      <div className="flex-1 text-[17px]" style={{ color: NAVY }}>
        <span className="font-medium">Your weekly goal: </span>
        <span className="font-bold">1/3 days</span>
      </div>
      <svg
        fill="none"
        height={22}
        stroke={NAVY}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2.2}
        viewBox="0 0 24 24"
        width={22}
      >
        <path d="m9 6 6 6-6 6" />
      </svg>
    </div>
  );
}

function ShortCard({
  background,
  label,
  children,
}: {
  background: string;
  label: string;
  children?: ReactNode;
}) {
  return (
    <div
      className="relative h-[182px] w-[136px] flex-shrink-0 overflow-hidden rounded-[18px]"
      style={{ background }}
    >
      {children}
      <div
        className="absolute inset-x-0 bottom-0 h-2/3"
        style={{
          background:
            "linear-gradient(to top, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0) 100%)",
        }}
      />
      <div className="absolute inset-x-0 bottom-0 p-3 font-bold text-[15px] text-white leading-tight">
        {label}
      </div>
    </div>
  );
}

function SmarterSection() {
  return (
    <div className="mt-10">
      <h2 className="font-bold text-[26px] leading-tight" style={{ color: NAVY }}>
        Smarter in 5 minutes
      </h2>
      <p className="mt-2 text-[15px] leading-snug" style={{ color: MUTED }}>
        Shorts help you learn something new every day. Be quick, today's set
        disappears at midnight.
      </p>
      <div className="-mr-7 mt-5 flex gap-3 overflow-x-auto pr-7 [&::-webkit-scrollbar]:hidden">
        <ShortCard
          background="linear-gradient(160deg, #f2c14a 0%, #e8a93b 100%)"
          label="Be Brave, Be Vulnerable"
        >
          <svg
            className="absolute bottom-12 left-1/2 -translate-x-1/2"
            fill="none"
            height={92}
            viewBox="0 0 70 92"
            width={70}
          >
            <circle cx="38" cy="14" fill="#1f3a8a" r="9" />
            <path d="M27 30h22l4 30H23l4-30Z" fill="#2b59c9" />
            <rect fill="#15235e" height="30" rx="3" width="8" x="29" y="60" />
            <rect fill="#15235e" height="30" rx="3" width="8" x="40" y="60" />
            <rect
              fill="#f4e6c4"
              height="16"
              rx="2"
              transform="rotate(-6 33 46)"
              width="26"
              x="20"
              y="38"
            />
            <path
              d="M20 40h26M20 45h26"
              stroke="#b89a52"
              strokeWidth="1.4"
            />
          </svg>
        </ShortCard>
        <ShortCard
          background="linear-gradient(160deg, #b7b1a8 0%, #6e6862 100%)"
          label="Why You Should Drop Perfecti..."
        >
          <div
            className="absolute top-0 left-1/2 h-12 w-3 -translate-x-1/2"
            style={{ background: "rgba(30,26,22,0.65)" }}
          />
          <div
            className="absolute left-1/2 top-10 h-8 w-px -translate-x-1/2"
            style={{ background: "rgba(245,240,235,0.85)" }}
          />
          <div
            className="absolute left-1/2 top-[68px] h-9 w-11 -translate-x-1/2 rounded-b-[14px] rounded-t-sm"
            style={{ background: "rgba(248,244,238,0.92)" }}
          />
        </ShortCard>
        <ShortCard
          background="linear-gradient(160deg, #8e7bd6 0%, #6f5fc0 100%)"
          label="What Skating Innovation is T..."
        >
          <div className="absolute inset-x-2.5 top-3 space-y-1.5">
            <p className="font-semibold text-[8px] text-white leading-tight">
              Tony Hawk is a legend. What innovation is he best known for?
            </p>
            <div className="rounded bg-white/80 px-1.5 py-1 text-[6px] text-[#3a3160]">
              Attaching wheels to a surfboard
            </div>
            <div className="rounded bg-white/80 px-1.5 py-1 text-[6px] text-[#3a3160]">
              Inventing bowl skating
            </div>
            <div className="rounded bg-white/60 px-1.5 py-1 text-[6px] text-[#3a3160]">
              Landing the first "900"
            </div>
          </div>
        </ShortCard>
      </div>
    </div>
  );
}

function BlinkOfDay() {
  return (
    <div className="mt-10">
      <div className="flex items-start justify-between">
        <h2
          className="font-bold text-[26px] leading-tight"
          style={{ color: NAVY }}
        >
          Your Blink of the day
        </h2>
        <svg
          fill="none"
          height={24}
          stroke="#2f6bff"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.9}
          viewBox="0 0 24 24"
          width={24}
        >
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
      </div>
      <p className="mt-2 text-[15px]" style={{ color: MUTED }}>
        Picked for you, based on what you like
      </p>
      <div
        className="-mx-7 mt-5 grid h-[360px] place-items-center rounded-t-[20px]"
        style={{ background: "linear-gradient(165deg, #5aa743 0%, #3f8a30 100%)" }}
      >
        <div
          className="flex w-[180px] flex-col items-center gap-2 rounded-[12px] px-5 py-7 text-center text-white"
          style={{ background: "linear-gradient(165deg, #4f9b38 0%, #357a28 100%)" }}
        >
          <span className="font-semibold text-[11px] tracking-[0.2em]">
            NAPOLEON HILL
          </span>
          <span className="font-serif font-bold text-[26px] leading-7">
            Think and Grow Rich
          </span>
          <svg className="mt-4" fill="none" height={44} viewBox="0 0 60 44" width={60}>
            <rect fill="#e8b53a" height="7" rx="1" width="9" x="22" y="13" />
            <rect fill="#f0c84e" height="6" rx="1" width="11" x="21" y="20" />
            <rect fill="#e8b53a" height="6" rx="1" width="13" x="20" y="26" />
            <path d="M8 32h44l-6 9H14l-6-9Z" fill="#ffffff" />
            <path d="M30 4v9" stroke="#cfe6c2" strokeWidth="1.6" />
            <circle cx="30" cy="4" fill="#f0c84e" r="2.4" />
          </svg>
        </div>
      </div>
    </div>
  );
}

function PhoneScreen() {
  return (
    <div
      className="pointer-events-auto absolute inset-0 overflow-y-auto bg-white [&::-webkit-scrollbar]:hidden"
      style={{ scrollbarWidth: "none" }}
    >
      <StatusBar />
      <div className="px-7">
        <TopActions />
        <h1
          className="mt-7 font-extrabold text-[40px] leading-none"
          style={{ color: NAVY }}
        >
          Home
        </h1>
        <WeeklyGoal />
        <SmarterSection />
        <BlinkOfDay />
      </div>
    </div>
  );
}

function GlassDockDemo() {
  return (
    <div className="flex w-full justify-center">
      <GlassDock
        accentColor="#0a84ff"
        align="bottom"
        className="h-[760px] w-full max-w-[440px] rounded-[44px] shadow-[0_30px_70px_-25px_rgba(10,30,45,0.6)] ring-1 ring-black/10"
        defaultValue="home"
        glass={DOCK_GLASS}
        hoverColor="#1c1c1e"
        idleColor="#3a3d42"
        items={ITEMS}
        pillColor="rgba(255,255,255,0.92)"
        tintBlur={16}
      >
        <PhoneScreen />
      </GlassDock>
    </div>
  );
}

export { GlassDockDemo };
