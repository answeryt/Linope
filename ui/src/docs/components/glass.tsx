import { GlassDemo } from "@/docs/demos/glass-demo";
import glassDemoSource from "@/docs/demos/glass-demo.tsx?raw";
import { GlassVideoExample } from "@/docs/demos/glass-video-example";
import glassVideoExampleSource from "@/docs/demos/glass-video-example.tsx?raw";
import type { ComponentDoc } from "@/docs/types";

const glassDoc: ComponentDoc = {
  slug: "glass",
  title: "Glass",
  description:
    "The core lens engine. It refracts its own children through an SVG feDisplacementMap, so text stays selectable and links stay clickable under the lens. Every element marked data-glass-lens becomes a movable refracting region. Works in Chromium, Safari, and Firefox.",
  registryName: "glass",
  demo: GlassDemo,
  demoSource: glassDemoSource,
  props: [
    {
      title: "Glass",
      rows: [
        {
          name: "lens",
          type: "ReactNode",
          defaultValue: "required",
          description:
            "Layer rendered above the content. Every element inside it marked with data-glass-lens becomes a refracting lens whose position, size, and border radius are tracked each frame.",
        },
        {
          name: "scaleX / scaleY",
          type: "number",
          defaultValue: "0.1",
          description:
            "Refraction strength per axis, as a fraction of the container width.",
        },
        {
          name: "tint",
          type: "number",
          defaultValue: "0",
          description:
            "Liquid Glass tint from 0 (ultra clear) to 1 (fully tinted). Raises a frosted backdrop inside the lens and softens the refraction, like the iOS 27 appearance slider.",
        },
        {
          name: "tintBlur",
          type: "number",
          defaultValue: "12",
          description: "Backdrop blur in px reached at full tint.",
        },
        {
          name: "tintColor",
          type: "string",
          defaultValue: "theme",
          description:
            "Tint color as an r,g,b triple, for example 255,255,255. Defaults to white in light mode and a dark gray in dark mode.",
        },
        {
          name: "chroma",
          type: "number",
          defaultValue: "0.2",
          description: "Chromatic aberration fringe along the lens edges.",
        },
        {
          name: "depth",
          type: "number",
          defaultValue: "6",
          description:
            "Width of the edge falloff band in px, the zone where the bend ramps up.",
        },
        {
          name: "domeDepth",
          type: "number",
          defaultValue: "0",
          description: "Curvature of the lens dome. 0 keeps the center flat.",
        },
        {
          name: "splay",
          type: "number",
          defaultValue: "1",
          description: "Direction of the edge bend, from inward 0 to outward 1.",
        },
        {
          name: "blur",
          type: "number",
          defaultValue: "0",
          description: "Blur in px applied only inside the lens.",
        },
        {
          name: "glow",
          type: "number",
          defaultValue: "0.12",
          description: "Strength of the baked specular glow.",
        },
        {
          name: "edgeHighlight",
          type: "number",
          defaultValue: "0.3",
          description: "Strength of the bright rim along the lens edge.",
        },
        {
          name: "specularAngle",
          type: "number",
          defaultValue: "45",
          description: "Angle of the specular highlight in degrees.",
        },
        {
          name: "specularStrength",
          type: "number",
          defaultValue: "1",
          description: "Multiplier for the specular highlight pass.",
        },
        {
          name: "mapSize",
          type: "number",
          defaultValue: "256",
          description: "Pixel resolution of the generated displacement map.",
        },
        {
          name: "maxDisplacement",
          type: "number",
          defaultValue: "Infinity",
          description: "Upper bound for the displacement in px.",
        },
        {
          name: "resolution",
          type: "number",
          defaultValue: "1",
          description: "Supersampling factor for the filtered content.",
        },
        {
          name: "reveal",
          type: "boolean",
          defaultValue: "false",
          description:
            "Render only the lens regions instead of compositing them over the visible content.",
        },
        {
          name: "dynamicsRef",
          type: "RefObject<GlassDynamics>",
          defaultValue: "undefined",
          description:
            "Imperative per-frame overrides for zoom, depth multiplier, and map dimensions, used for gel deformation.",
        },
      ],
    },
    {
      title: "GlassSurface",
      rows: [
        {
          name: "tint",
          type: "number",
          defaultValue: "0.5",
          description:
            "Tint of the panel from 0 (clear) to 1 (opaque), same scale as the Glass tint prop.",
        },
        {
          name: "tintColor",
          type: "string",
          defaultValue: "theme",
          description: "Tint color as an r,g,b triple.",
        },
        {
          name: "blur",
          type: "number",
          defaultValue: "8",
          description: "Backdrop blur of the panel in px.",
        },
        {
          name: "saturation",
          type: "number",
          defaultValue: "1.5",
          description: "Backdrop saturation boost, the iOS material color lift.",
        },
        {
          name: "radius",
          type: "number",
          defaultValue: "16",
          description: "Corner radius of the panel in px.",
        },
        {
          name: "specular",
          type: "boolean",
          defaultValue: "true",
          description: "Render the specular rim highlights.",
        },
        {
          name: "handleRef",
          type: "RefObject<GlassSurfaceHandle>",
          defaultValue: "undefined",
          description:
            "Imperative handle with setTintLift for animating press and focus tint changes without re-rendering.",
        },
      ],
    },
  ],
  examples: [
    {
      title: "Video player",
      description:
        "Each control is its own lens refracting the live video underneath. Per lens overrides come from data-glass-* attributes.",
      component: GlassVideoExample,
      source: glassVideoExampleSource,
      minHeight: 360,
    },
  ],
};

export { glassDoc };
