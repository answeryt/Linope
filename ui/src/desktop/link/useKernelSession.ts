import { useCallback, useEffect, useReducer } from "react";
import {
  appendErrorMessage,
  appendLoopUser,
  appendUserTurn,
  bindRequest,
  dequeueConversation,
  enqueueConversation,
  initialUiState,
  markUnavailable,
  openConversation,
  reduceKernelEvent,
  type UiConversation,
  type UiState,
} from "./state";
import { parseKernelEvent, type KernelEvent } from "./protocol";

type Action =
  | { type: "event"; event: KernelEvent }
  | { type: "user"; text: string; requestId: string }
  | { type: "loop-user"; conversationId: string; capability: string; pid?: string; text: string }
  | { type: "open"; conversation: UiConversation; text?: string }
  | { type: "enqueue"; conversationId: string; text: string }
  | { type: "dequeue"; conversationId: string }
  | { type: "bind-request"; requestId: string; conversationId: string }
  | { type: "error"; text: string; conversationId?: string }
  | { type: "unavailable"; text: string };

const conversationPhase = new Map<string, { requestId: string; stage: "sending" | "live" }>();
let conversationSeq = 0;

function reduceSession(state: UiState, action: Action): UiState {
  switch (action.type) {
    case "event":
      return reduceKernelEvent(state, action.event);
    case "user":
      return appendUserTurn(state, action.text, undefined, action.requestId);
    case "loop-user":
      return appendLoopUser(state, action);
    case "open":
      return openConversation(state, action.conversation, action.text);
    case "enqueue":
      return enqueueConversation(state, action.conversationId, action.text);
    case "dequeue":
      return dequeueConversation(state, action.conversationId);
    case "bind-request":
      return bindRequest(state, action.requestId, action.conversationId);
    case "error":
      return appendErrorMessage(state, action.text, action.conversationId);
    case "unavailable":
      return markUnavailable(state, action.text);
  }
}

export function useKernelSession() {
  const [state, dispatch] = useReducer(reduceSession, undefined, initialUiState);
  const api = typeof window === "undefined" ? undefined : window.linopeKernel;

  useEffect(() => {
    if (!api) {
      dispatch({
        type: "unavailable",
        text: "当前运行环境没有 Electron 后端连接能力。",
      });
      return;
    }

    return api.onEvent((rawEvent) => {
      try {
        dispatch({ type: "event", event: parseKernelEvent(rawEvent) });
      } catch (error) {
        dispatch({
          type: "error",
          text: error instanceof Error ? error.message : String(error),
        });
      }
    });
  }, [api]);

  const sessionReady = useCallback(() => {
    if (!api) {
      dispatch({
        type: "unavailable",
        text: "当前运行环境没有 Electron 后端连接能力。",
      });
      return false;
    }
    if (state.connection === "closed" || state.connection === "unavailable") {
      dispatch({ type: "error", text: "后端会话已关闭，请重新启动桌面应用。" });
      return false;
    }
    return true;
  }, [api, state.connection]);

  const acceptText = useCallback(
    (text: string) => {
      const value = text.trim();
      if (!value || !sessionReady()) return "";
      return value;
    },
    [sessionReady],
  );

  const send = useCallback(
    (text: string) => {
      const value = acceptText(text);
      if (!value || !api) return false;
      if (state.status === "running" || state.chatRequest) {
        dispatch({ type: "error", text: "上一条请求仍在处理中，请稍候。" });
        return false;
      }
      const requestId = api.chat.send(value);
      dispatch({ type: "user", text: value, requestId });
      return true;
    },
    [acceptText, api, state.chatRequest, state.status],
  );

  const modelChanges = useCallback(
    (changes?: Array<{ topic: string; value: string }>, scope = "") => {
      const next = [...(changes ?? [])];
      if (scope) next.push({ topic: "scope", value: scope });
      return next.length ? next : undefined;
    },
    [],
  );

  const newConversation = useCallback(
    (capability: string, changes?: Array<{ topic: string; value: string }>, text = "") => {
      if (!sessionReady() || !api) return "";
      conversationSeq += 1;
      const id = `c${conversationSeq}`;
      const requestId = api.process.create({
        capability,
        changes: modelChanges(changes, `chat-${id}`),
      });
      const conversation: UiConversation = {
        awaiting: Boolean(text.trim()),
        capability,
        createRequestId: requestId,
        id,
        pid: "",
        queue: [],
      };
      dispatch({ type: "open", conversation, text: text.trim() });
      return id;
    },
    [api, modelChanges, sessionReady],
  );

  const sendToConversation = useCallback(
    (conversationId: string, text: string) => {
      const value = acceptText(text);
      if (!value || !api) return false;
      const conversation = state.conversations.find((item) => item.id === conversationId);
      if (!conversation) {
        dispatch({ type: "error", text: "这个对话已经不在了。" });
        return false;
      }
      dispatch({
        type: "loop-user",
        capability: conversation.capability,
        conversationId,
        pid: conversation.pid || undefined,
        text: value,
      });
      dispatch({ type: "enqueue", conversationId, text: value });
      return true;
    },
    [acceptText, api, state.conversations],
  );

  useEffect(() => {
    if (state.connection === "closed") {
      conversationPhase.clear();
      return;
    }
    const active = new Set(state.activeTurns.values());
    for (const [id, phase] of conversationPhase) {
      const conversation = state.conversations.find((item) => item.id === id);
      if (!conversation) {
        conversationPhase.delete(id);
        continue;
      }
      const live = Boolean(conversation.pid) && active.has(conversation.pid);
      if (phase.stage === "sending" && live) {
        conversationPhase.set(id, { requestId: phase.requestId, stage: "live" });
      }
      if (phase.stage === "live" && !live) conversationPhase.delete(id);
      if (
        phase.stage === "sending" &&
        state.actionStates.get(phase.requestId)?.status === "failed"
      ) {
        conversationPhase.delete(id);
      }
    }
    if (!api) return;
    for (const conversation of state.conversations) {
      const text = conversation.queue[0];
      if (!conversation.pid || !text) continue;
      if (conversationPhase.has(conversation.id)) continue;
      if (active.has(conversation.pid)) continue;
      const requestId = api.process.send({ pid: Number(conversation.pid), text });
      conversationPhase.set(conversation.id, { requestId, stage: "sending" });
      dispatch({ type: "dequeue", conversationId: conversation.id });
      dispatch({ type: "bind-request", conversationId: conversation.id, requestId });
    }
  }, [api, state.actionStates, state.activeTurns, state.connection, state.conversations, state.requestConversation]);

  const stop = useCallback(() => {
    api?.stop();
  }, [api]);

  const createProcess = useCallback(
    (input: Parameters<LinopeKernelApi["process"]["create"]>[0]) => {
      if (!api) {
        dispatch({
          type: "unavailable",
          text: "当前运行环境没有 Electron 后端连接能力。",
        });
        return false;
      }
      return api.process.create(input);
    },
    [api],
  );

  const sendToProcess = useCallback(
    (input: Parameters<LinopeKernelApi["process"]["send"]>[0]) => {
      if (!api) {
        dispatch({
          type: "unavailable",
          text: "当前运行环境没有 Electron 后端连接能力。",
        });
        return false;
      }
      return api.process.send(input);
    },
    [api],
  );

  const loadEnvironment = useCallback(
    (input: Parameters<LinopeKernelApi["environment"]["load"]>[0]) => {
      if (!api) {
        dispatch({
          type: "unavailable",
          text: "当前运行环境没有 Electron 后端连接能力。",
        });
        return false;
      }
      return api.environment.load(input);
    },
    [api],
  );

  const saveSecret = useCallback(
    (input: Parameters<LinopeKernelApi["environment"]["saveSecret"]>[0]) => {
      if (!api) {
        dispatch({
          type: "unavailable",
          text: "当前运行环境没有 Electron 后端连接能力。",
        });
        return false;
      }
      return api.environment.saveSecret(input);
    },
    [api],
  );

  const configureModel = useCallback(
    (input: Parameters<LinopeKernelApi["model"]["configure"]>[0]) => {
      if (!api) {
        dispatch({
          type: "unavailable",
          text: "当前运行环境没有 Electron 后端连接能力。",
        });
        return false;
      }
      return api.model.configure(input);
    },
    [api],
  );

  const loadModelCatalog = useCallback(() => {
    if (!api) {
      dispatch({
        type: "unavailable",
        text: "当前运行环境没有 Electron 后端连接能力。",
      });
      return false;
    }
    return api.model.catalog();
  }, [api]);

  return {
    actions: {
      configureModel,
      createProcess,
      loadModelCatalog,
      loadEnvironment,
      saveSecret,
      sendToProcess,
    },
    canSend: Boolean(api) && state.connection === "ready" && state.status === "ready" && !state.chatRequest,
    connection: state.connection,
    conversations: state.conversations,
    modelCatalog: state.modelCatalog,
    newConversation,
    send,
    sendToConversation,
    state,
    stop,
    turns: state.turns,
  };
}
