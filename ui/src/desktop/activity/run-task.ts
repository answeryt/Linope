import { activityTaskStore, type ActivityTaskStart } from "./task-store";

export type ActivityTaskHandle = {
  id: string;
  update: (patch: Parameters<typeof activityTaskStore.update>[1]) => void;
  finish: (detail?: Parameters<typeof activityTaskStore.finish>[1]) => void;
  fail: (error: string) => void;
  end: () => void;
};

export function startActivityTask(input: ActivityTaskStart): ActivityTaskHandle {
  activityTaskStore.start(input);
  return {
    end: () => activityTaskStore.end(input.id),
    fail: (error) => activityTaskStore.fail(input.id, error),
    finish: (detail) => activityTaskStore.finish(input.id, detail),
    id: input.id,
    update: (patch) => activityTaskStore.update(input.id, patch),
  };
}
