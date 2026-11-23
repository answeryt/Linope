import { useCallback, useRef, useState } from "react";
import { Glass } from "@/components/ui/glass";
import { Back15, Fwd15, Pause, Play } from "@/components/docs/icons";

const W = 480;
const H = 270;
const PLAY_SIZE = 111 * 0.75;
const SKIP_SIZE = 65 * 0.75;
const GAP = 24;
const BAR_H = 30;
const BAR_MARGIN = 12;
const BAR_PAD = 14;
const SKIP_SECONDS = 15;

const MAIN_DEPTH = Math.round(0.16 * (PLAY_SIZE / 2) * 10) / 10;
const SIDE_DEPTH = Math.round(0.14 * (SKIP_SIZE / 2) * 10) / 10;
const BAR_DEPTH = 0.5 * (BAR_H / 2);
const MAIN_SCALE = 0.07;
const SIDE_MUL = 0.04 / MAIN_SCALE;
const BAR_MUL = 0.04 / MAIN_SCALE;

const pressTransition =
  "width 0.3s cubic-bezier(0.22, 1.15, 0.36, 1.06), height 0.3s cubic-bezier(0.22, 1.15, 0.36, 1.06), transform 0.3s cubic-bezier(0.22, 1.15, 0.36, 1.06)";

function GlassVideoExample() {
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [entered, setEntered] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const barRef = useRef<HTMLDivElement | null>(null);
  const fillRef = useRef<HTMLDivElement | null>(null);
  const scrubbing = useRef(false);
  const wasPlaying = useRef(false);
  const [pressed, setPressed] = useState<"back" | "play" | "fwd" | null>(null);

  const visible = ready && (hovered || !entered);

  const attachVideo = useCallback((el: HTMLVideoElement | null) => {
    videoRef.current = el;
    if (el && el.readyState >= el.HAVE_CURRENT_DATA) {
      setReady(true);
    }
  }, []);

  const attachBar = useCallback((el: HTMLDivElement | null) => {
    barRef.current = el;
    if (!el) {
      return;
    }
    let raf = 0;
    const tick = () => {
      const v = videoRef.current;
      if (v && Number.isFinite(v.duration) && v.duration > 0 && fillRef.current) {
        fillRef.current.style.width = `${(v.currentTime / v.duration) * 100}%`;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const toggle = () => {
    const v = videoRef.current;
    if (!v) {
      return;
    }
    if (v.paused) {
      v.play().catch(() => undefined);
    } else {
      v.pause();
    }
  };

  const skip = (delta: number) => {
    const v = videoRef.current;
    if (!v || !Number.isFinite(v.duration)) {
      return;
    }
    v.currentTime = Math.min(Math.max(v.currentTime + delta, 0), v.duration);
  };

  const seek = (clientX: number) => {
    const v = videoRef.current;
    const bar = barRef.current;
    if (!(v && bar) || !Number.isFinite(v.duration) || v.duration <= 0) {
      return;
    }
    const rect = bar.getBoundingClientRect();
    const frac = Math.min(
      Math.max((clientX - rect.left - BAR_PAD) / (rect.width - 2 * BAR_PAD), 0),
      1
    );
    const t = frac * v.duration;
    if (typeof v.fastSeek === "function") {
      v.fastSeek(t);
    } else {
      v.currentTime = t;
    }
  };

  const buttonStyle = (size: number, isPressed: boolean) => ({
    width: size,
    height: size,
    borderRadius: size / 2,
    transform: isPressed ? "scale(0.8)" : "scale(1)",
    transition: pressTransition,
    pointerEvents: "auto" as const,
  });

  const lensMark = (
    size: number,
    order: number,
    overrides: Record<string, number>,
    isPressed: boolean
  ) => (
    <div
      data-glass-lens
      style={{
        width: size * (isPressed ? 0.8 : 1),
        height: size * (isPressed ? 0.8 : 1),
        borderRadius: 999,
        order,
        transition: pressTransition,
      }}
      {...Object.fromEntries(
        Object.entries(overrides).map(([k, v]) => [`data-glass-${k}`, v])
      )}
    />
  );

  return (
    <div
      className="relative isolate max-w-full overflow-hidden rounded-[12px]"
        onMouseEnter={() => {
          setHovered(true);
          setEntered(true);
        }}
        onMouseLeave={() => setHovered(false)}
        style={{ width: W, aspectRatio: `${W} / ${H}` }}
      >
        <Glass
          blur={0.3}
          chroma={0}
          className="absolute inset-0"
          depth={MAIN_DEPTH}
          domeDepth={35}
          edgeHighlight={0.5}
          edgeWidth={2.5}
          glow={0}
          glowSpread={0.5}
          lens={
            visible ? (
              <div
                className="absolute inset-0"
                style={{ pointerEvents: "none" }}
              >
                <div className="absolute inset-0 flex items-center justify-center" style={{ gap: GAP }}>
                  {lensMark(
                    SKIP_SIZE,
                    1,
                    {
                      depth: SIDE_DEPTH,
                      "dome-depth": 40,
                      "edge-highlight": 0.49,
                      "edge-width": 2,
                      mul: SIDE_MUL,
                    },
                    pressed === "back"
                  )}
                  {lensMark(PLAY_SIZE, 2, {}, pressed === "play")}
                  {lensMark(
                    SKIP_SIZE,
                    3,
                    {
                      depth: SIDE_DEPTH,
                      "dome-depth": 40,
                      "edge-highlight": 0.49,
                      "edge-width": 2,
                      mul: SIDE_MUL,
                    },
                    pressed === "fwd"
                  )}
                </div>
                <div
                  data-glass-lens
                  data-glass-depth={BAR_DEPTH}
                  data-glass-dome-depth={0}
                  data-glass-edge-highlight={0.25}
                  data-glass-edge-width={2}
                  data-glass-mul={BAR_MUL}
                  style={{
                    position: "absolute",
                    bottom: BAR_MARGIN,
                    left: BAR_MARGIN,
                    right: BAR_MARGIN,
                    height: BAR_H,
                    borderRadius: BAR_H / 2,
                  }}
                />
              </div>
            ) : null
          }
          scaleX={MAIN_SCALE}
          scaleY={MAIN_SCALE}
          specularAngle={30}
          specularStrength={1}
          splay={1}
        >
          <video
            autoPlay
            className="h-full w-full object-cover"
            loop
            muted
            onCanPlay={() => setReady(true)}
            onPause={() => setPlaying(false)}
            onPlay={() => setPlaying(true)}
            playsInline
            ref={attachVideo}
            src="/aurora.mp4"
          />
        </Glass>
        <div
          className="absolute inset-0 flex items-center justify-center text-white"
          style={{
            gap: GAP,
            opacity: visible ? 1 : 0,
            filter: visible ? "blur(0px)" : "blur(4px)",
            transition: "opacity 0.25s ease-out, filter 0.25s ease-out",
            pointerEvents: visible ? "auto" : "none",
          }}
        >
          <button
            aria-label={`Rewind ${SKIP_SECONDS} seconds`}
            className="flex shrink-0 cursor-pointer items-center justify-center"
            onClick={() => skip(-SKIP_SECONDS)}
            onPointerDown={() => setPressed("back")}
            onPointerLeave={() => setPressed(null)}
            onPointerUp={() => setPressed(null)}
            style={{ ...buttonStyle(SKIP_SIZE, pressed === "back"), order: 1 }}
            type="button"
          >
            <Back15 style={{ width: "70.83%", height: "67.83%" }} />
          </button>
          <button
            aria-label={playing ? "Pause" : "Play"}
            className="flex shrink-0 cursor-pointer items-center justify-center"
            onClick={toggle}
            onPointerDown={() => setPressed("play")}
            onPointerLeave={() => setPressed(null)}
            onPointerUp={() => setPressed(null)}
            style={{ ...buttonStyle(PLAY_SIZE, pressed === "play"), order: 2 }}
            type="button"
          >
            {playing ? (
              <Pause style={{ width: "49.55%", height: "49.55%" }} />
            ) : (
              <Play style={{ width: "49.55%", height: "49.55%" }} />
            )}
          </button>
          <button
            aria-label={`Forward ${SKIP_SECONDS} seconds`}
            className="flex shrink-0 cursor-pointer items-center justify-center"
            onClick={() => skip(SKIP_SECONDS)}
            onPointerDown={() => setPressed("fwd")}
            onPointerLeave={() => setPressed(null)}
            onPointerUp={() => setPressed(null)}
            style={{ ...buttonStyle(SKIP_SIZE, pressed === "fwd"), order: 3 }}
            type="button"
          >
            <Fwd15 style={{ width: "70.83%", height: "67.83%" }} />
          </button>
        </div>
        <div
          aria-label="Seek"
          className="absolute flex cursor-pointer touch-none items-center"
          onPointerDown={(e) => {
            e.preventDefault();
            e.currentTarget.setPointerCapture(e.pointerId);
            scrubbing.current = true;
            const v = videoRef.current;
            wasPlaying.current = !!v && !v.paused;
            v?.pause();
            seek(e.clientX);
          }}
          onPointerMove={(e) => {
            if (scrubbing.current) {
              seek(e.clientX);
            }
          }}
          onPointerUp={() => {
            scrubbing.current = false;
            if (wasPlaying.current) {
              videoRef.current?.play().catch(() => undefined);
            }
          }}
          ref={attachBar}
          role="slider"
          style={{
            bottom: BAR_MARGIN,
            left: BAR_MARGIN,
            right: BAR_MARGIN,
            height: BAR_H,
            paddingLeft: BAR_PAD,
            paddingRight: BAR_PAD,
            opacity: visible ? 1 : 0,
            transition: "opacity 0.25s ease-out",
            pointerEvents: visible ? "auto" : "none",
          }}
        >
          <div className="pointer-events-none relative h-[6px] flex-1 rounded-[3px] bg-white/30">
            <div
              className="pointer-events-none absolute top-0 left-0 h-full rounded-[inherit] bg-white"
              ref={fillRef}
              style={{ width: "0%" }}
            />
          </div>
        </div>
    </div>
  );
}

export { GlassVideoExample };
