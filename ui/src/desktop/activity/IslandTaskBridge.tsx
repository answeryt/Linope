import { useEffect, useRef, useSyncExternalStore } from "react";
import { useIslandActions } from "@/lib/island";
import { activityTaskStore, type ActivityTask } from "./task-store";

function statusText(task: ActivityTask): string {
  if (task.status === "pending") return "等待中";
  if (task.status === "success") return "已完成";
  if (task.status === "error") return task.error || "失败";
  if (task.progress === undefined) return "进行中";
  return `进行中 ${Math.round(task.progress * 100)}%`;
}

function taskContent(task: ActivityTask) {
  const status = statusText(task);
  const detail = task.detail ?? task.error ?? null;
  return {
    compact: {
      leading: <span style={{ fontSize: 13, fontWeight: 600 }}>{task.label}</span>,
      trailing: <span style={{ fontSize: 12, opacity: 0.72 }}>{status}</span>,
    },
    minimal: <span style={{ fontSize: 13, fontWeight: 600 }}>{task.label}</span>,
    expanded: {
      leading: (
        <span style={{ marginLeft: 12, fontSize: 15, fontWeight: 600 }}>
          {task.label}
        </span>
      ),
      bottom: detail ? <span style={{ display: "block", marginLeft: 12 }}>{detail}</span> : null,
    },
  };
}

function activityId(taskId: string): string {
  return `task:${taskId}`;
}

function IslandTaskBridge() {
  const tasks = useSyncExternalStore(
    activityTaskStore.subscribe,
    activityTaskStore.getSnapshot,
    activityTaskStore.getSnapshot,
  );
  const island = useIslandActions();
  const previousStatus = useRef(new Map<string, ActivityTask["status"]>());
  const finishTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  useEffect(() => {
    const visibleIds = new Set(tasks.map((task) => task.id));
    for (const task of tasks) {
      const id = activityId(task.id);
      const content = taskContent(task);
      const previous = previousStatus.current.get(task.id);
      if (previous === undefined) {
        island.start({
          ...content,
          alert: false,
          group: task.group || "background-tasks",
          id,
          label: task.label,
          onPress: () => island.expand(id),
          priority: task.priority + (task.status === "error" ? 100 : 0),
        });
      } else {
        island.update(id, {
          ...content,
          alert:
            previous !== task.status &&
            (task.status === "success" || task.status === "error"),
          label: task.label,
          priority: task.priority + (task.status === "error" ? 100 : 0),
        });
        if (
          previous !== task.status &&
          (task.status === "success" || task.status === "error")
        ) {
          const oldTimer = finishTimers.current.get(task.id);
          if (oldTimer) clearTimeout(oldTimer);
          finishTimers.current.set(
            task.id,
            setTimeout(() => {
              finishTimers.current.delete(task.id);
              activityTaskStore.end(task.id);
            }, 3000),
          );
        }
      }
      previousStatus.current.set(task.id, task.status);
    }

    for (const [taskId] of previousStatus.current) {
      if (!visibleIds.has(taskId)) {
        island.end(activityId(taskId));
        previousStatus.current.delete(taskId);
      }
    }
  }, [island, tasks]);

  useEffect(
    () => () => {
      for (const timer of finishTimers.current.values()) clearTimeout(timer);
      finishTimers.current.clear();
    },
    [],
  );

  return null;
}

export { IslandTaskBridge };
