import {
  type AnchorHTMLAttributes,
  type MouseEvent,
  type ReactNode,
  useSyncExternalStore,
} from "react";

const listeners = new Set<() => void>();

function notify() {
  for (const fn of listeners) {
    fn();
  }
}

function readPath(): string {
  return window.location.pathname || "/";
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  window.addEventListener("popstate", fn);
  return () => {
    listeners.delete(fn);
    window.removeEventListener("popstate", fn);
  };
}

function useRoute(): string {
  return useSyncExternalStore(subscribe, readPath);
}

function navigate(path: string) {
  if (path !== window.location.pathname) {
    window.history.pushState(null, "", path);
    notify();
  }
  window.scrollTo(0, 0);
}

interface LinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  children: ReactNode;
  to: string;
}

function isModifiedEvent(e: MouseEvent<HTMLAnchorElement>): boolean {
  return e.metaKey || e.ctrlKey || e.shiftKey || e.altKey;
}

function Link({ to, children, onClick, target, ...props }: LinkProps) {
  return (
    <a
      href={to}
      onClick={(e) => {
        onClick?.(e);
        if (
          e.defaultPrevented ||
          e.button !== 0 ||
          isModifiedEvent(e) ||
          (target && target !== "_self")
        ) {
          return;
        }
        e.preventDefault();
        navigate(to);
      }}
      target={target}
      {...props}
    >
      {children}
    </a>
  );
}

export { Link, navigate, useRoute };
