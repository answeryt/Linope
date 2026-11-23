"use client";

import {
  generateLensMap,
  isSafariBrowser,
  useGlassDark,
  useHydrated,
} from "@/components/ui/glass";
import { cn } from "@/lib/utils";
import {
  type ComponentProps,
  type RefObject,
  useEffect,
  useId,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

const TINT_MAX_ALPHA = 0.4;
const MIN_VEIL = 0.07;
const MIN_BLUR = 2.5;
const MAP_SIZE = 256;
const MAP_CACHE_LIMIT = 48;
const GLOW = 0.16;
const EDGE = 0.85;
const SPECULAR_STRENGTH = 1.7;

const surfaceMapCache = new Map<string, string>();

function clamp01(v: number): number {
  return v < 0 ? 0 : v > 1 ? 1 : v;
}

function refractionSupported(): boolean {
  if (typeof navigator === "undefined") {
    return false;
  }
  return (
    /(Chrome|Chromium|Edg|OPR)\//.test(navigator.userAgent) &&
    !isSafariBrowser()
  );
}

function surfaceMap(
  w: number,
  h: number,
  radius: number,
  rim: number
): string {
  const key = `${w}|${h}|${radius}|${rim}`;
  const cached = surfaceMapCache.get(key);
  if (cached !== undefined) {
    return cached;
  }
  const url =
    generateLensMap({
      halfW: w / 2,
      halfH: h / 2,
      radius,
      depth: rim,
      domeDepth: 0,
      splay: 1,
      specularAngle: 45,
      glowStrength: GLOW,
      glowSpread: 1,
      glowExponent: 1.5,
      edgeStrength: EDGE,
      edgeWidth: 2,
      edgeExponent: 1.5,
      size: MAP_SIZE,
      sdfBoundary: true,
      edgeFalloff: true,
    }) ?? "";
  surfaceMapCache.set(key, url);
  if (surfaceMapCache.size > MAP_CACHE_LIMIT) {
    const first = surfaceMapCache.keys().next().value;
    if (first !== undefined) {
      surfaceMapCache.delete(first);
    }
  }
  return url;
}

interface GlassSurfaceHandle {
  setTintLift(delta: number): void;
}

interface GlassSurfaceProps extends ComponentProps<"div"> {
  blur?: number;
  chroma?: number;
  handleRef?: RefObject<GlassSurfaceHandle | null>;
  radius?: number;
  saturation?: number;
  specular?: boolean;
  tint?: number;
  tintColor?: string;
}

function GlassSurface({
  blur = 12,
  chroma = 0,
  handleRef,
  radius = 16,
  saturation = 1.5,
  specular = true,
  tint = 0.5,
  tintColor,
  className,
  style,
  children,
  ...props
}: GlassSurfaceProps) {
  const dark = useGlassDark();
  const t = clamp01(tint);
  const tintRGB = tintColor ?? (dark ? "58,58,62" : "255,255,255");
  const tintRef = useRef<HTMLDivElement | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const feImageRef = useRef<SVGFEImageElement | null>(null);
  const dispRefs = useRef<(SVGFEDisplacementMapElement | null)[]>([
    null,
    null,
    null,
  ]);
  const baseId = useId().replace(/[^a-zA-Z0-9-]/g, "");
  const filterId = `${baseId}-surface`;
  const [supported] = useState(refractionSupported);
  const refract = useHydrated() && supported;
  const chromaOn = chroma > 0;

  const blurPx = Math.max(t * blur * 0.5, MIN_BLUR);
  const dispFade = 1 - 0.3 * t;

  useImperativeHandle(
    handleRef,
    () => ({
      setTintLift(delta: number) {
        if (tintRef.current) {
          tintRef.current.style.background = `rgba(${tintRGB},${Math.max(clamp01(t + delta) * TINT_MAX_ALPHA, MIN_VEIL)})`;
        }
      },
    }),
    [t, tintRGB]
  );

  useEffect(() => {
    if (!refract) {
      return;
    }
    const node = rootRef.current;
    if (!node) {
      return;
    }
    let lastKey = "";
    const update = () => {
      const w = node.offsetWidth;
      const h = node.offsetHeight;
      if (w < 4 || h < 4) {
        return;
      }
      const half = Math.min(w, h) / 2;
      const r = Math.max(0, Math.min(radius, w / 2, h / 2));
      const rim = Math.max(6, Math.min(0.18 * Math.min(w, h), 24, half - 2));
      const key = `${w}|${h}|${r}|${rim}`;
      if (key !== lastKey) {
        lastKey = key;
        const img = feImageRef.current;
        if (img) {
          img.setAttribute("href", surfaceMap(w, h, r, rim));
          img.setAttribute("width", String(w));
          img.setAttribute("height", String(h));
        }
      }
      const base = Math.min(0.17 * Math.min(w, h), 26) * dispFade;
      const scales = chromaOn
        ? [base * (1 + 0.22 * chroma), base * (1 + 0.11 * chroma), base]
        : [base, base, base];
      dispRefs.current.forEach((el, i) => {
        el?.setAttribute("scale", String(scales[i] ?? base));
      });
    };
    const observer = new ResizeObserver(update);
    observer.observe(node);
    update();
    return () => observer.disconnect();
  }, [refract, radius, chroma, chromaOn, dispFade]);

  const filterParts: string[] = [];
  if (refract) {
    filterParts.push(`url(#${filterId})`);
  }
  if (blurPx > 0.05) {
    filterParts.push(`blur(${blurPx}px)`);
  }
  const sat = 1 + (saturation - 1) * t;
  if (sat > 1.001) {
    filterParts.push(`saturate(${sat})`);
  }
  const backdropFilter = filterParts.length ? filterParts.join(" ") : "none";

  const rim = dark
    ? "inset 0 1px 1px 0 rgba(255,255,255,0.55), inset 0 0 0 1px rgba(255,255,255,0.2), inset 0 -12px 24px -16px rgba(255,255,255,0.4), 0 18px 44px -12px rgba(0,0,0,0.55)"
    : "inset 0 1px 1px 0 rgba(255,255,255,0.95), inset 0 0 0 1px rgba(255,255,255,0.45), inset 0 -12px 24px -16px rgba(255,255,255,0.6), 0 16px 40px -10px rgba(0,0,0,0.22)";
  const sheen = dark
    ? "linear-gradient(135deg, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0) 32%, rgba(255,255,255,0) 68%, rgba(255,255,255,0.07) 100%)"
    : "linear-gradient(135deg, rgba(255,255,255,0.28) 0%, rgba(255,255,255,0) 34%, rgba(255,255,255,0) 66%, rgba(255,255,255,0.14) 100%)";

  return (
    <div
      className={cn("relative", className)}
      ref={rootRef}
      style={{ borderRadius: radius, ...style }}
      {...props}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-[inherit]"
        style={{
          backdropFilter,
          WebkitBackdropFilter: backdropFilter,
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-[inherit]"
        ref={tintRef}
        style={{
          background: `rgba(${tintRGB},${Math.max(t * TINT_MAX_ALPHA, MIN_VEIL)})`,
        }}
      />
      {specular ? (
        <>
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 rounded-[inherit]"
            style={{ background: sheen }}
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 rounded-[inherit]"
            style={{ boxShadow: rim }}
          />
        </>
      ) : null}
      {refract ? (
        <svg aria-hidden="true" className="absolute h-0 w-0" focusable="false">
          <defs>
            <filter
              colorInterpolationFilters="sRGB"
              filterUnits="objectBoundingBox"
              height="1"
              id={filterId}
              primitiveUnits="userSpaceOnUse"
              width="1"
              x="0"
              y="0"
            >
              <feImage
                preserveAspectRatio="none"
                ref={feImageRef}
                result="map"
                x="0"
                y="0"
              />
              {chromaOn ? (
                <>
                  <feDisplacementMap
                    in="SourceGraphic"
                    in2="map"
                    ref={(el) => {
                      dispRefs.current[0] = el;
                    }}
                    result="dR"
                    scale="0"
                    xChannelSelector="R"
                    yChannelSelector="G"
                  />
                  <feColorMatrix
                    in="dR"
                    result="cR"
                    type="matrix"
                    values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0"
                  />
                  <feDisplacementMap
                    in="SourceGraphic"
                    in2="map"
                    ref={(el) => {
                      dispRefs.current[1] = el;
                    }}
                    result="dG"
                    scale="0"
                    xChannelSelector="R"
                    yChannelSelector="G"
                  />
                  <feColorMatrix
                    in="dG"
                    result="cG"
                    type="matrix"
                    values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0"
                  />
                  <feDisplacementMap
                    in="SourceGraphic"
                    in2="map"
                    ref={(el) => {
                      dispRefs.current[2] = el;
                    }}
                    result="dB"
                    scale="0"
                    xChannelSelector="R"
                    yChannelSelector="G"
                  />
                  <feColorMatrix
                    in="dB"
                    result="cB"
                    type="matrix"
                    values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0"
                  />
                  <feComposite
                    in="cR"
                    in2="cG"
                    k1="0"
                    k2="1"
                    k3="1"
                    k4="0"
                    operator="arithmetic"
                    result="cRG"
                  />
                  <feComposite
                    in="cRG"
                    in2="cB"
                    k1="0"
                    k2="1"
                    k3="1"
                    k4="0"
                    operator="arithmetic"
                    result="refr"
                  />
                </>
              ) : (
                <feDisplacementMap
                  in="SourceGraphic"
                  in2="map"
                  ref={(el) => {
                    dispRefs.current[0] = el;
                  }}
                  result="refr"
                  scale="0"
                  xChannelSelector="R"
                  yChannelSelector="G"
                />
              )}
              {specular ? (
                <>
                  <feColorMatrix
                    in="map"
                    result="spec"
                    type="matrix"
                    values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 1 0 -0.5019607843"
                  />
                  <feComposite
                    in="spec"
                    in2="refr"
                    k1="0"
                    k2={SPECULAR_STRENGTH}
                    k3="1"
                    k4="0"
                    operator="arithmetic"
                  />
                </>
              ) : null}
            </filter>
          </defs>
        </svg>
      ) : null}
      <div className="relative h-full w-full rounded-[inherit]">{children}</div>
    </div>
  );
}

export { GlassSurface };
export type { GlassSurfaceHandle, GlassSurfaceProps };
