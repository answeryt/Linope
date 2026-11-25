import { useSyncExternalStore } from "react";

const STORAGE_KEY = "linope.installed-apps";
const retiredIds = new Set(["loop:pi"]);

type StoredInstalledApp = {
  id: string;
  installedAt: number;
  lastUsed: number;
  useCount: number;
};

type InstalledApp = StoredInstalledApp;

function isStoredInstalledApp(value: unknown): value is StoredInstalledApp {
  if (!value || typeof value !== "object") return false;
  const row = value as Partial<StoredInstalledApp>;
  return (
    typeof row.id === "string" &&
    row.id.length > 0 &&
    typeof row.installedAt === "number" &&
    Number.isFinite(row.installedAt) &&
    typeof row.lastUsed === "number" &&
    Number.isFinite(row.lastUsed) &&
    typeof row.useCount === "number" &&
    Number.isFinite(row.useCount) &&
    row.useCount >= 0
  );
}

function sortInstalledApps(apps: InstalledApp[]) {
  return [...apps].sort(
    (left, right) =>
      right.useCount - left.useCount ||
      right.lastUsed - left.lastUsed ||
      right.installedAt - left.installedAt ||
      left.id.localeCompare(right.id),
  );
}

function load(): InstalledApp[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const stored = sortInstalledApps(parsed.filter(isStoredInstalledApp));
    const visible = stored.filter((app) => !retiredIds.has(app.id));
    if (visible.length !== stored.length) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(visible));
      } catch {
        // 存储不可用时仍然不把已下线的应用留在本次列表里。
      }
    }
    return visible;
  } catch {
    return [];
  }
}

let state = load();
const listeners = new Set<() => void>();

function commit(next: InstalledApp[]) {
  state = sortInstalledApps(next);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // 存储不可用时仍然保留本次会话里的状态。
  }
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getState() {
  return state;
}

function now() {
  return Date.now();
}

function installApp(id: string) {
  if (!id || retiredIds.has(id) || state.some((app) => app.id === id)) return;
  const timestamp = now();
  commit([
    ...state,
    {
      id,
      installedAt: timestamp,
      lastUsed: 0,
      useCount: 0,
    },
  ]);
}

function markAppUsed(id: string) {
  if (!id) return;
  const timestamp = now();
  let changed = false;
  const next = state.map((app) => {
    if (app.id !== id) return app;
    changed = true;
    return {
      ...app,
      lastUsed: timestamp,
      useCount: app.useCount + 1,
    };
  });
  if (changed) commit(next);
}

function useInstalledApps() {
  return useSyncExternalStore(subscribe, getState, getState);
}

export type { InstalledApp };
export { installApp, markAppUsed, useInstalledApps };
