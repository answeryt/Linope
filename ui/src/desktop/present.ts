import { dialogGlass, dialogSurface } from "@/desktop/dialog/glass";

const PAINT_FRAMES = 2;

function applySurface(element: HTMLElement) {
  element.style.background = dialogSurface.background;
  element.style.backdropFilter = dialogSurface.backdropFilter;
  element.style.setProperty("-webkit-backdrop-filter", dialogSurface.WebkitBackdropFilter);
}

/** Compile the shared panel blur, clip, and the sidebar width spring offscreen. */
function warmCompositor() {
  const root = document.createElement("div");
  root.setAttribute("aria-hidden", "true");
  root.style.position = "fixed";
  root.style.left = "-10000px";
  root.style.top = "0";
  root.style.overflow = "hidden";
  root.style.pointerEvents = "none";

  const panel = document.createElement("div");
  applySurface(panel);
  panel.style.width = "320px";
  panel.style.height = "180px";
  panel.style.borderRadius = `${dialogGlass.radius}px`;
  panel.style.boxShadow = "0 12px 34px rgba(12, 16, 30, 0.22)";
  panel.style.transform = "translate3d(0, 0, 0)";
  panel.style.clipPath = `inset(0 0 0 0 round ${dialogGlass.radius}px)`;

  const rail = document.createElement("div");
  applySurface(rail);
  rail.style.width = "18px";
  rail.style.height = "112px";
  rail.style.borderRadius = "0 22px 22px 0";
  rail.style.boxShadow = "0 12px 34px rgba(12, 16, 30, 0.22)";
  rail.style.transform = "translateZ(0)";

  root.append(panel, rail);
  document.body.append(root);
  panel.getBoundingClientRect();
  rail.getBoundingClientRect();

  requestAnimationFrame(() => {
    panel.style.transform = "translate3d(8px, 0, 0)";
    panel.style.clipPath = `inset(8% 8% 8% 8% round ${dialogGlass.radius}px)`;
    rail.style.width = "248px";
    requestAnimationFrame(() => {
      panel.style.transform = "translate3d(0, 0, 0)";
      panel.style.clipPath = `inset(0 0 0 0 round ${dialogGlass.radius}px)`;
      rail.style.width = "18px";
      requestAnimationFrame(() => {
        root.remove();
      });
    });
  });
}

function scheduleWarm() {
  if (typeof requestIdleCallback === "function") {
    requestIdleCallback(() => warmCompositor(), { timeout: 800 });
    return;
  }
  setTimeout(warmCompositor, 300);
}

/** Let the hidden window composite the glass, then ask Electron to show it. */
function presentDesktop(): () => void {
  let cancelled = false;
  let frame = 0;
  let left = PAINT_FRAMES;
  const step = () => {
    if (cancelled) {
      return;
    }
    left -= 1;
    if (left > 0) {
      frame = requestAnimationFrame(step);
      return;
    }
    window.linopeKernel?.desktop?.presented();
    scheduleWarm();
  };
  frame = requestAnimationFrame(step);
  return () => {
    cancelled = true;
    cancelAnimationFrame(frame);
  };
}

export { presentDesktop };
