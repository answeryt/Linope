import { loopAppId, routeDraft } from "./route.ts";
import {
  appendLoopUser,
  appendUserTurn,
  dequeueConversation,
  enqueueConversation,
  hostedMessages,
  initialUiState,
  openConversation,
  reduceKernelEvent,
} from "./state.ts";
import type { KernelEvent } from "./protocol.ts";

function event(kind: string, data: Record<string, unknown>, extra: Partial<KernelEvent> = {}): KernelEvent {
  return {
    data,
    kind,
    seq: 1,
    version: 1,
    ...extra,
  };
}

const loops = { "loop:linope": "agent_loop", "tool:read": "" };

const closed = routeDraft(null, { "loop:linope": "agent_loop" });
if (closed.kind !== "choose") throw new Error("a closed tool must ask where the sentence goes");

const selected = routeDraft("loop:linope", { "loop:linope": "agent_loop" });
if (selected.kind !== "loop" || selected.capability !== "agent_loop") {
  throw new Error("an open linope window must stay on that loop");
}
if (loopAppId(loops) !== "loop:linope") throw new Error("linope app id was not found");

let state = appendUserTurn(initialUiState(), "普通对话");
state = reduceKernelEvent(state, event("model.delta", { text: "聊天回复" }));
if (state.turns.map((item) => item.text).join("") !== "普通对话聊天回复") {
  throw new Error("chat text did not stay in the conversation");
}
if (Object.keys(state.hosted).length !== 0) throw new Error("chat text leaked into a loop");

state = appendLoopUser(state, { capability: "agent_loop", text: "搜索天气" });
state = reduceKernelEvent(
  state,
  event("process.started", { capability: "agent_loop" }, { pid: 20 }),
);
state = reduceKernelEvent(
  state,
  event("model.delta", { text: "晴" }, { pid: 20 }),
);
state = reduceKernelEvent(
  state,
  event("task.step", {
    leader: true,
    pc: "wait_tool",
    registers: { question: "搜索天气", tool: "search" },
    task_id: "20",
  }, { pid: 20 }),
);
state = reduceKernelEvent(
  state,
  event("task.step", {
    leader: false,
    pc: "wait_tool",
    registers: { tool: "read", path: "note.txt" },
    task_id: "20.2",
  }, { pid: 20 }),
);

const messages = hostedMessages(state, "agent_loop", "20").map((item) => item.text);
if (messages.join("") !== "搜索天气晴") throw new Error(`loop text went to the wrong place: ${messages.join("|")}`);
if (state.turns.some((item) => item.text.includes("搜索天气") || item.text.includes("晴"))) {
  throw new Error("loop text leaked into the conversation");
}

const leader = state.tasks.find((task) => task.id === "20");
const reader = state.tasks.find((task) => task.id === "20.2");
if (leader?.registers.tool !== "search" || leader.registers.question !== "搜索天气") {
  throw new Error("leader registers were not stored");
}
if (reader?.registers.path !== "note.txt" || "question" in (reader?.registers ?? {})) {
  throw new Error("task registers were mixed");
}

let parallel = openConversation(
  initialUiState(),
  {
    awaiting: true,
    capability: "agent_loop",
    createRequestId: "create-1",
    id: "c1",
    pid: "",
    queue: [],
  },
  "甲",
);
parallel = reduceKernelEvent(
  parallel,
  event("process.started", { capability: "agent_loop" }, { pid: 20, request_id: "create-1" }),
);
parallel = openConversation(parallel, {
  awaiting: false,
  capability: "agent_loop",
  createRequestId: "create-2",
  id: "c2",
  pid: "",
  queue: [],
});
parallel = appendLoopUser(parallel, { capability: "agent_loop", conversationId: "c2", text: "乙" });
parallel = reduceKernelEvent(
  parallel,
  event("process.started", { capability: "agent_loop" }, { pid: 21, request_id: "create-2" }),
);
parallel = reduceKernelEvent(parallel, event("model.delta", { text: "二" }, { pid: 21 }));
parallel = reduceKernelEvent(parallel, event("model.delta", { text: "一" }, { pid: 20 }));
const firstConversation = hostedMessages(parallel, "agent_loop", "20").map((item) => item.text).join("");
const secondConversation = hostedMessages(parallel, "agent_loop", "21").map((item) => item.text).join("");
if (firstConversation !== "甲一") throw new Error(`first conversation mixed: ${firstConversation}`);
if (secondConversation !== "乙二") throw new Error(`second conversation mixed: ${secondConversation}`);

parallel = enqueueConversation(parallel, "c1", "丙");
parallel = enqueueConversation(parallel, "c1", "丁");
const queued = parallel.conversations.find((item) => item.id === "c1");
if (queued?.queue.join(",") !== "甲,丙,丁") throw new Error(`queue order: ${queued?.queue.join(",")}`);
parallel = dequeueConversation(parallel, "c1");
parallel = dequeueConversation(parallel, "c1");
const remaining = parallel.conversations.find((item) => item.id === "c1");
if (remaining?.queue.join(",") !== "丁") throw new Error(`dequeue order: ${remaining?.queue.join(",")}`);

const quiet = reduceKernelEvent(
  parallel,
  event("command.completed", { command: "list", value: null }, { request_id: "listed" }),
);
if (quiet.turns.length !== 0) throw new Error("an empty command completion was shown");

console.log("task routing checks passed");
