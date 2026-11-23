import type { ReactNode } from "react";

export type ActivityTaskStatus = "pending" | "running" | "success" | "error";

export type ActivityTask = {
  id: string;
  label: string;
  group: string;
  priority: number;
  status: ActivityTaskStatus;
  progress?: number;
  detail?: ReactNode;
  error?: string;
  requestId?: string;
};

export type ActivityTaskStart = Omit<ActivityTask, "status"> & {
  status?: ActivityTaskStatus;
};

let tasks: readonly ActivityTask[] = [];
const listeners = new Set<() => void>();

function publish(next: readonly ActivityTask[]) {
  tasks = next;
  for (const listener of listeners) listener();
}

export const activityTaskStore = {
  getSnapshot(): readonly ActivityTask[] {
    return tasks;
  },

  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  start(input: ActivityTaskStart): void {
    const next: ActivityTask = {
      ...input,
      status: input.status ?? "pending",
    };
    const exists = tasks.some((task) => task.id === input.id);
    publish(exists ? tasks.map((task) => (task.id === input.id ? { ...task, ...next } : task)) : [...tasks, next]);
  },

  update(id: string, patch: Partial<Omit<ActivityTask, "id">>): void {
    publish(tasks.map((task) => (task.id === id ? { ...task, ...patch } : task)));
  },

  finish(id: string, detail?: ReactNode): void {
    activityTaskStore.update(id, { detail, status: "success" });
  },

  fail(id: string, error: string): void {
    activityTaskStore.update(id, { error, status: "error" });
  },

  end(id: string): void {
    publish(tasks.filter((task) => task.id !== id));
  },
};
