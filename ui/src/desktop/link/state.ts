import type { KernelEvent } from "./protocol";

export type UiTurn = {
  id: string;
  role: "assistant" | "error" | "system" | "user";
  reasoning?: string;
  rawText?: string;
  requestId?: string;
  stream?: boolean;
  text: string;
  turnId?: string;
};

export type UiProcess = {
  id: string;
  capability: string;
  activity: "waiting" | "busy" | "away";
};

export type UiTask = {
  changed: string[];
  id: string;
  leader: boolean;
  pc: string;
  pid: string;
  registers: Record<string, unknown>;
};

export type ModelPlugin = {
  capability: string;
  card_id: string;
  plugin: string;
  provider: string;
  interface: string;
  model: string;
  base_url: string;
  api_key_env: string;
  changes: string[];
  parameters: Record<string, unknown>;
  context_limit: number;
  ready: boolean;
  error: string | null;
};

export type ActionLifecycle =
  | { status: "accepted" }
  | { status: "completed"; result?: unknown }
  | { status: "failed"; error: string };

export type UiConversation = {
  id: string;
  capability: string;
  pid: string;
  createRequestId: string;
  queue: string[];
  awaiting: boolean;
};

export type UiState = {
  connection: "ready" | "closed" | "unavailable";
  cwd: string;
  clerk: "here" | "away";
  failedRequests: Set<string>;
  capabilityCalls: Set<string>;
  actionStates: Map<string, ActionLifecycle>;
  modelCatalog: ModelPlugin[];
  processes: UiProcess[];
  tasks: UiTask[];
  conversations: UiConversation[];
  requestConversation: Map<string, string>;
  hosted: Record<string, UiTurn[]>;
  chatRequest: string;
  status: "ready" | "running";
  turns: UiTurn[];
  activeTurns: Map<string, string>;
  turnRequests: Map<string, string>;
};

let nextTurnId = 0;

function createTurnId(prefix: string): string {
  nextTurnId += 1;
  return `${prefix}-${nextTurnId}`;
}

export function initialUiState(cwd = ""): UiState {
  return {
    activeTurns: new Map(),
    clerk: "here",
    connection: "ready",
    cwd,
    failedRequests: new Set(),
    capabilityCalls: new Set(),
    actionStates: new Map(),
    modelCatalog: [],
    processes: [],
    tasks: [],
    conversations: [],
    requestConversation: new Map(),
    hosted: {},
    chatRequest: "",
    status: "ready",
    turns: [],
    turnRequests: new Map(),
  };
}

export function appendUserTurn(
  state: UiState,
  text: string,
  id = createTurnId("user"),
  requestId = "",
): UiState {
  return {
    ...state,
    chatRequest: requestId || state.chatRequest,
    status: "running",
    turns: [...state.turns, { id, role: "user", text }],
  };
}

export function appendLoopUser(
  state: UiState,
  input: { capability: string; conversationId?: string; pid?: string; text: string },
  id = createTurnId("user"),
): UiState {
  const key = input.pid
    ? input.pid
    : input.conversationId
      ? `conversation:${input.conversationId}`
      : `capability:${input.capability}`;
  return {
    ...state,
    hosted: {
      ...state.hosted,
      [key]: [...(state.hosted[key] ?? []), { id, role: "user", text: input.text }],
    },
  };
}

export function openConversation(
  state: UiState,
  conversation: UiConversation,
  text = "",
): UiState {
  let next: UiState = {
    ...state,
    conversations: [...state.conversations, conversation],
    requestConversation: new Map(state.requestConversation),
  };
  if (conversation.createRequestId) {
    next.requestConversation.set(conversation.createRequestId, conversation.id);
  }
  if (!text) return next;
  next = appendLoopUser(next, {
    capability: conversation.capability,
    conversationId: conversation.id,
    text,
  });
  return enqueueConversation(next, conversation.id, text);
}

export function enqueueConversation(state: UiState, conversationId: string, text: string): UiState {
  return {
    ...state,
    conversations: state.conversations.map((conversation) =>
      conversation.id === conversationId
        ? { ...conversation, awaiting: true, queue: [...conversation.queue, text] }
        : conversation,
    ),
  };
}

export function dequeueConversation(state: UiState, conversationId: string): UiState {
  return {
    ...state,
    conversations: state.conversations.map((conversation) =>
      conversation.id === conversationId
        ? { ...conversation, awaiting: true, queue: conversation.queue.slice(1) }
        : conversation,
    ),
  };
}

export function bindRequest(state: UiState, requestId: string, conversationId: string): UiState {
  const requestConversation = new Map(state.requestConversation);
  requestConversation.set(requestId, conversationId);
  const conversation = state.conversations.find((item) => item.id === conversationId);
  if (!conversation) return { ...state, requestConversation };
  const keys = [conversation.pid, `conversation:${conversation.id}`, `capability:${conversation.capability}`].filter(
    (key) => key,
  );
  for (const key of keys) {
    const list = state.hosted[key];
    if (!list) continue;
    const index = list.findIndex((item) => item.role === "user" && !item.requestId);
    if (index < 0) continue;
    return {
      ...state,
      hosted: {
        ...state.hosted,
        [key]: list.map((item, itemIndex) => (itemIndex === index ? { ...item, requestId } : item)),
      },
      requestConversation,
    };
  }
  return { ...state, requestConversation };
}

export function currentWindowLines(state: UiState, conversation: { id: string; pid: string } | null): string[] {
  const seen = new Set<string>();
  const lines: string[] = [];
  const take = (items: UiTurn[] | undefined) => {
    for (const item of items ?? []) {
      if (seen.has(item.id)) continue;
      seen.add(item.id);
      if (item.role !== "user" && item.role !== "assistant") continue;
      lines.push(item.text);
    }
  };
  if (!conversation) {
    take(state.turns);
    return lines;
  }
  take(state.hosted[`conversation:${conversation.id}`]);
  if (conversation.pid) take(state.hosted[conversation.pid]);
  return lines;
}

export function estimateTokens(text: string): number {
  if (!text) return 0;
  return Math.max(1, Math.floor((text.length + 3) / 4));
}

export function occupiedTokens(systemPrompt: string, lines: string[]): number {
  return lines.reduce((sum, line) => sum + estimateTokens(line), estimateTokens(systemPrompt));
}

export function hostedMessages(state: UiState, capability?: string, pid?: string): UiTurn[] {
  const seen = new Set<string>();
  const merged: UiTurn[] = [];
  const add = (items: UiTurn[] | undefined) => {
    for (const item of items ?? []) {
      if (seen.has(item.id)) continue;
      seen.add(item.id);
      merged.push(item);
    }
  };
  if (capability) add(state.hosted[`capability:${capability}`]);
  if (pid) add(state.hosted[pid]);
  for (const conversation of state.conversations) {
    if (capability && conversation.capability !== capability) continue;
    if (pid && conversation.pid && conversation.pid !== pid) continue;
    add(state.hosted[`conversation:${conversation.id}`]);
    if (conversation.pid) add(state.hosted[conversation.pid]);
  }
  return merged;
}

export function markUnavailable(state: UiState, text: string): UiState {
  return {
    ...state,
    connection: "unavailable",
    turns: appendMessage(state, "error", text),
  };
}

export function appendErrorMessage(state: UiState, text: string, conversationId = ""): UiState {
  const conversation = conversationId
    ? state.conversations.find((item) => item.id === conversationId)
    : undefined;
  const key = conversation
    ? conversation.pid || `conversation:${conversation.id}`
    : "";
  if (!key) {
    return {
      ...state,
      turns: appendMessage(state, "error", text),
    };
  }
  return {
    ...state,
    hosted: {
      ...state.hosted,
      [key]: [...(state.hosted[key] ?? []), { id: createTurnId("error"), role: "error", text }],
    },
  };
}

export function reduceKernelEvent(state: UiState, event: KernelEvent): UiState {
  const next: UiState = {
    ...state,
    activeTurns: new Map(state.activeTurns),
    failedRequests: new Set(state.failedRequests),
    capabilityCalls: new Set(state.capabilityCalls),
    actionStates: new Map(state.actionStates),
    conversations: state.conversations.map((conversation) => ({
      ...conversation,
      queue: [...conversation.queue],
    })),
    requestConversation: new Map(state.requestConversation),
    processes: state.processes.map((process) => ({ ...process })),
    tasks: state.tasks.map((task) => ({
      ...task,
      changed: [...task.changed],
      registers: { ...task.registers },
    })),
    hosted: Object.fromEntries(
      Object.entries(state.hosted).map(([key, items]) => [key, items.map((item) => ({ ...item }))]),
    ),
    turns: [...state.turns],
    turnRequests: new Map(state.turnRequests),
  };

  switch (event.kind) {
    case "session.started":
      next.clerk = "here";
      next.connection = "ready";
      next.cwd = textOf(event.data.cwd) || next.cwd;
      return next;
    case "session.closed":
      next.clerk = "away";
      next.connection = "closed";
      next.processes = [];
      next.tasks = [];
      next.hosted = {};
      next.conversations = [];
      next.requestConversation = new Map();
      next.activeTurns = new Map();
      next.turnRequests = new Map();
      next.capabilityCalls = new Set();
      next.chatRequest = "";
      next.status = "ready";
      return next;
    case "process.started": {
      if (event.pid === undefined) return next;
      const capability = textOf(event.data.capability);
      const pid = String(event.pid);
      upsertProcess(next, pid, capability, "waiting");
      const pendingKey = capability ? `capability:${capability}` : "";
      const pending = pendingKey ? next.hosted[pendingKey] : undefined;
      if (pending) {
        next.hosted[pid] = [...(next.hosted[pid] ?? []), ...pending];
        delete next.hosted[pendingKey];
      }
      const conversation =
        next.conversations.find(
          (item) => item.createRequestId && item.createRequestId === event.request_id && !item.pid,
        ) ?? next.conversations.find((item) => !item.pid && item.capability === capability);
      if (conversation) {
        conversation.pid = pid;
        const waitingKey = `conversation:${conversation.id}`;
        const waiting = next.hosted[waitingKey];
        if (waiting) {
          next.hosted[pid] = [...(next.hosted[pid] ?? []), ...waiting];
          delete next.hosted[waitingKey];
        }
      }
      return next;
    }
    case "process.activity":
      if (event.pid === undefined) return next;
      upsertProcess(
        next,
        String(event.pid),
        textOf(event.data.capability),
        activityOf(event.data.activity),
      );
      if (activityOf(event.data.activity) === "away") {
        const id = String(event.pid);
        next.processes = next.processes.filter((process) => process.id !== id);
        next.tasks = next.tasks.filter((task) => task.pid !== id);
      }
      return next;
    case "process.closed":
      if (event.pid !== undefined) {
        const id = String(event.pid);
        next.processes = next.processes.filter((process) => process.id !== id);
        next.tasks = next.tasks.filter((task) => task.pid !== id);
      }
      return next;
    case "task.step": {
      const task = taskOf(event, state.tasks);
      if (!task) return next;
      const index = next.tasks.findIndex((item) => item.id === task.id && item.pid === task.pid);
      if (index >= 0) next.tasks[index] = task;
      else next.tasks.push(task);
      return next;
    }
    case "turn.started":
      if (event.turn_id) {
        next.activeTurns.set(event.turn_id, event.pid !== undefined ? String(event.pid) : "");
        if (event.request_id) next.turnRequests.set(event.turn_id, event.request_id);
      }
      if (event.pid === undefined) next.status = "running";
      return next;
    case "model.delta":
      appendStreamTo(
        routeText(next, event),
        textOf(event.data.text),
        event.turn_id ?? "",
        requestIdOf(next, event),
      );
      return next;
    case "model.reasoning.delta":
      appendReasoningTo(
        routeText(next, event),
        textOf(event.data.text),
        event.turn_id ?? "",
        requestIdOf(next, event),
      );
      return next;
    case "turn.completed":
      if (event.turn_id) next.activeTurns.delete(event.turn_id);
      completeList(routeText(next, event), event, undefined, requestIdOf(next, event));
      if (event.turn_id) next.turnRequests.delete(event.turn_id);
      finishChat(next, event.request_id);
      finishConversation(next, event.pid);
      return next;
    case "command.completed":
      if (event.request_id && next.capabilityCalls.has(event.request_id)) {
        finishChat(next, event.request_id);
        return next;
      }
      if (textOf(event.data.command).startsWith("model run -- ")) {
        completeList(routeText(next, event), event, event.data.value, requestIdOf(next, event));
      } else {
        showCommandValue(next, event, routeText(next, event));
      }
      finishChat(next, event.request_id);
      return next;
    case "action.accepted":
      if (event.request_id) {
        next.actionStates.set(event.request_id, { status: "accepted" });
        if (event.data.action === "capability.call") next.capabilityCalls.add(event.request_id);
      }
      return next;
    case "command.failed":
      if (failureSeen(next, event)) return next;
      appendErrorTo(routeText(next, event), errorText(event.data.error) || errorText(event.data));
      finishChat(next, event.request_id);
      finishConversation(next, event.pid);
      return next;
    case "action.completed":
      if (event.request_id) {
        next.actionStates.set(event.request_id, {
          result: event.data.result,
          status: "completed",
        });
      }
      if (event.data.action === "model.catalog") {
        next.modelCatalog = modelCatalogOf(event.data.result);
      }
      return next;
    case "action.failed":
      if (event.request_id) {
        next.actionStates.set(event.request_id, {
          error: errorText(event.data.error) || "连接动作失败",
          status: "failed",
        });
      }
      if (
        event.data.action === "capability.call" ||
        (event.request_id !== undefined && next.capabilityCalls.has(event.request_id))
      ) {
        return next;
      }
      if (failureSeen(next, event)) return next;
      appendErrorTo(routeText(next, event), errorText(event.data.error) || "连接动作失败");
      finishChat(next, event.request_id);
      releaseConversation(next, event.request_id);
      return next;
    case "protocol.error":
    case "diagnostic":
      appendErrorTo(routeText(next, event), textOf(event.data.message) || "Invalid kernel event");
      return next;
    case "capability.notice":
      if (event.data.kind === "agent.progress") {
        appendSystemTo(routeText(next, event), textOf(event.data.text));
      }
      return next;
    default:
      return next;
  }
}

function completeList(
  list: UiTurn[],
  event: KernelEvent,
  completedResult: unknown | undefined,
  requestId: string,
): void {
  const turnId = event.turn_id ?? "";
  const error = event.data.error;
  if (error) {
    appendErrorTo(list, errorText(error), turnId ? placeIndex(list, turnId, requestId) : list.length);
    return;
  }

  const content = modelContent(
    completedResult === undefined ? event.data.result : completedResult,
  );
  if (!content.text && !content.reasoning) return;

  const index = streamingIndex(list, turnId);
  if (index >= 0) {
    const current = list[index];
    list[index] = {
      ...current,
      reasoning: content.reasoning || current.reasoning,
      stream: false,
      text: content.text || current.text,
      ...(turnId ? { turnId } : {}),
    };
    return;
  }
  const bubble: UiTurn = {
    id: createTurnId("assistant"),
    reasoning: content.reasoning || undefined,
    role: "assistant",
    text: content.text,
    ...(turnId ? { turnId } : {}),
  };
  if (!turnId) {
    list.push(bubble);
    return;
  }
  list.splice(placeIndex(list, turnId, requestId), 0, bubble);
}

function appendStreamTo(list: UiTurn[], text: string, turnId: string, requestId: string): void {
  if (!text) return;
  const index = streamingIndex(list, turnId);
  if (index >= 0) {
    const current = list[index];
    const rawText = `${current.rawText ?? current.text}${text}`;
    list[index] = {
      ...current,
      rawText,
      text: stripHiddenReasoning(rawText),
      ...(turnId ? { turnId } : {}),
    };
    return;
  }
  if (!turnId) {
    const last = list.at(-1);
    const rawText = `${last?.role === "assistant" ? last.rawText ?? last.text : ""}${text}`;
    list.push({
      id: createTurnId("assistant"),
      rawText,
      role: "assistant",
      stream: true,
      text: stripHiddenReasoning(rawText),
    });
    return;
  }
  const rawText = text;
  list.splice(placeIndex(list, turnId, requestId), 0, {
    id: createTurnId("assistant"),
    rawText,
    role: "assistant",
    stream: true,
    text: stripHiddenReasoning(rawText),
    turnId,
  });
}

function appendReasoningTo(list: UiTurn[], text: string, turnId: string, requestId: string): void {
  if (!text) return;
  const index = streamingIndex(list, turnId);
  if (index >= 0) {
    const current = list[index];
    list[index] = {
      ...current,
      reasoning: `${current.reasoning ?? ""}${text}`,
      ...(turnId ? { turnId } : {}),
    };
    return;
  }
  const bubble: UiTurn = {
    id: createTurnId("assistant"),
    reasoning: text,
    role: "assistant",
    stream: true,
    text: "",
    ...(turnId ? { turnId } : {}),
  };
  if (!turnId) {
    list.push(bubble);
    return;
  }
  list.splice(placeIndex(list, turnId, requestId), 0, bubble);
}

function streamingIndex(list: UiTurn[], turnId: string): number {
  if (turnId) {
    for (let index = list.length - 1; index >= 0; index -= 1) {
      const item = list[index];
      if (item?.role === "assistant" && item.stream && item.turnId === turnId) return index;
    }
    return -1;
  }
  const last = list.at(-1);
  return last?.role === "assistant" && last.stream ? list.length - 1 : -1;
}

function placeIndex(list: UiTurn[], turnId: string, requestId: string): number {
  if (!turnId || !requestId) return list.length;
  const anchor = list.findIndex((item) => item.role === "user" && item.requestId === requestId);
  if (anchor < 0) return list.length;
  let index = anchor + 1;
  while (index < list.length && list[index]?.turnId === turnId) index += 1;
  return index;
}

function requestIdOf(state: UiState, event: KernelEvent): string {
  const recorded = event.turn_id ? state.turnRequests.get(event.turn_id) : "";
  return recorded || event.request_id || "";
}

function appendErrorTo(list: UiTurn[], text: string, at = list.length): void {
  if (text) {
    list.splice(at, 0, { id: createTurnId("error"), role: "error", text });
  }
}

function appendSystemTo(list: UiTurn[], text: string): void {
  if (text) {
    list.push({ id: createTurnId("system"), role: "system", text });
  }
}

function finishChat(state: UiState, requestId: string | undefined): void {
  if (!requestId || requestId !== state.chatRequest) return;
  state.chatRequest = "";
  state.status = "ready";
}

function finishConversation(state: UiState, pid: number | undefined): void {
  if (pid === undefined) return;
  const id = String(pid);
  for (const activePid of state.activeTurns.values()) {
    if (activePid === id) return;
  }
  for (const conversation of state.conversations) {
    if (conversation.pid === id && conversation.queue.length === 0) {
      conversation.awaiting = false;
    }
  }
}

function releaseConversation(state: UiState, requestId: string | undefined): void {
  if (!requestId) return;
  const conversationId = state.requestConversation.get(requestId);
  if (!conversationId) return;
  const conversation = state.conversations.find((item) => item.id === conversationId);
  if (!conversation) return;
  conversation.awaiting = false;
  if (!conversation.pid && requestId === conversation.createRequestId) {
    conversation.queue = [];
  }
}

function routeText(state: UiState, event: KernelEvent): UiTurn[] {
  if (event.pid !== undefined) return hostedList(state, String(event.pid));
  const conversationId = event.request_id ? state.requestConversation.get(event.request_id) : "";
  if (conversationId) {
    const conversation = state.conversations.find((item) => item.id === conversationId);
    return hostedList(state, conversation?.pid || `conversation:${conversationId}`);
  }
  return state.turns;
}

function hostedList(state: UiState, key: string): UiTurn[] {
  const found = state.hosted[key];
  if (found) return found;
  const created: UiTurn[] = [];
  state.hosted[key] = created;
  return created;
}

function failureSeen(state: UiState, event: KernelEvent): boolean {
  const requestId = event.request_id;
  if (!requestId) return false;
  if (state.failedRequests.has(requestId)) return true;
  state.failedRequests.add(requestId);
  return false;
}

function modelCatalogOf(value: unknown): ModelPlugin[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item): ModelPlugin[] => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return [];
    const row = item as Record<string, unknown>;
    if (
      typeof row.capability !== "string" ||
      typeof row.card_id !== "string" ||
      typeof row.plugin !== "string" ||
      typeof row.provider !== "string" ||
      typeof row.interface !== "string" ||
      typeof row.model !== "string" ||
      typeof row.base_url !== "string" ||
      typeof row.api_key_env !== "string" ||
      !Array.isArray(row.changes) ||
      !row.changes.every((change) => typeof change === "string") ||
      !row.parameters ||
      typeof row.parameters !== "object" ||
      Array.isArray(row.parameters) ||
      typeof row.context_limit !== "number" ||
      typeof row.ready !== "boolean" ||
      (row.error !== null && typeof row.error !== "string")
    ) {
      return [];
    }
    return [
      {
        api_key_env: row.api_key_env,
        base_url: row.base_url,
        capability: row.capability,
        card_id: row.card_id,
        changes: row.changes,
        context_limit: row.context_limit,
        error: row.error,
        interface: row.interface,
        model: row.model,
        parameters: row.parameters as Record<string, unknown>,
        plugin: row.plugin,
        provider: row.provider,
        ready: row.ready,
      },
    ];
  });
}

function appendMessage(
  state: UiState,
  role: UiTurn["role"],
  text: string,
): UiTurn[] {
  return text
    ? [...state.turns, { id: createTurnId(role), role, text }]
    : state.turns;
}

function showCommandValue(state: UiState, event: KernelEvent, list = state.turns): void {
  const command = textOf(event.data.command);
  if (!command || command.startsWith("process start")) return;
  const value = event.data.value;
  if (value === undefined || value === null || value === 0) return;
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  appendSystemTo(list, text);
}

function upsertProcess(
  state: UiState,
  id: string,
  capability: string,
  activity: UiProcess["activity"],
): void {
  const found = state.processes.find((process) => process.id === id);
  if (found) {
    if (capability) found.capability = capability;
    found.activity = activity;
  } else {
    state.processes.push({ activity, capability, id });
  }
}

function activityOf(value: unknown): UiProcess["activity"] {
  const activity = textOf(value);
  if (activity === "working" || activity === "busy") return "busy";
  if (activity === "sleeping" || activity === "waiting") return "waiting";
  return "away";
}

function modelContent(value: unknown): { reasoning: string; text: string } {
  const payload = typeof value === "string" ? parseJson(value) : value;
  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    const blocks = (payload as { blocks?: unknown }).blocks;
    if (Array.isArray(blocks)) {
      const content = blocks.reduce(
        (result, block) => {
          if (!block || typeof block !== "object" || Array.isArray(block)) return result;
          const typed = block as { text?: unknown; type?: unknown };
          const text = textOf(typed.text);
          if (typed.type === "text") result.text.push(text);
          if (typed.type === "reasoning") result.reasoning.push(text);
          return result;
        },
        { reasoning: [] as string[], text: [] as string[] },
      );
      return {
        reasoning: content.reasoning.filter(Boolean).join("\n"),
        text: stripHiddenReasoning(content.text.filter(Boolean).join("\n")),
      };
    }
  }
  if (typeof value === "string") {
    return { reasoning: "", text: stripHiddenReasoning(value) };
  }
  return {
    reasoning: "",
    text: value === undefined || value === null ? "" : JSON.stringify(value),
  };
}

function stripHiddenReasoning(value: string): string {
  return value
    .replace(
      /<\s*(think|analysis|reasoning)\b[^>]*>[\s\S]*?(?:<\s*\/\s*\1\s*>|$)/gi,
      "",
    )
    .replace(/<\s*\/?\s*(think|analysis|reasoning)\b[^>]*>/gi, "");
}

function parseJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function taskOf(event: KernelEvent, previous: UiTask[]): UiTask | null {
  if (event.pid === undefined) return null;
  const id = textOf(event.data.task_id);
  if (!id) return null;
  const registers = recordOf(event.data.registers);
  const pid = String(event.pid);
  const prior = previous.find((item) => item.id === id && item.pid === pid);
  return {
    changed: changedKeys(prior?.registers, registers),
    id,
    leader: event.data.leader === true,
    pc: textOf(event.data.pc) || "idle",
    pid,
    registers,
  };
}

function recordOf(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? { ...(value as Record<string, unknown>) }
    : {};
}

function changedKeys(
  previous: Record<string, unknown> | undefined,
  next: Record<string, unknown>,
): string[] {
  if (!previous) return [];
  const keys = new Set([...Object.keys(previous), ...Object.keys(next)]);
  return [...keys].filter((key) => stable(previous[key]) !== stable(next[key]));
}

function stable(value: unknown): string {
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function textOf(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function errorText(value: unknown): string {
  if (value && typeof value === "object") {
    const error = value as { code?: unknown; message?: unknown };
    if (typeof error.message === "string") return error.message;
    if (typeof error.code === "string") return error.code;
  }
  return textOf(value);
}
