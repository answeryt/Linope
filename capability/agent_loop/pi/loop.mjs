/**
 * One Pi session. Tool execution, extensions, and the transcript are Pi's.
 * The model request is supplied by the caller, which writes a kernel command line.
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { Agent } from "@earendil-works/pi-agent-core";
import { AssistantMessageEventStream } from "@earendil-works/pi-ai/utils/event-stream";
import { getCurrentSystemMessage, getCurrentTools } from "@earendil-works/pi-ai/utils/transcript";
import { getSystemMessageText } from "@earendil-works/pi-ai/utils/text";
import {
  AgentSession,
  DefaultResourceLoader,
  SessionManager,
  SettingsManager,
  convertToLlm,
  createCodemodeExtension,
  createMcpExtension,
  createToolSearchExtension,
  getAgentDir,
} from "@earendil-works/pi-coding-agent";

const PREAMBLE =
  "我是使用了 Pi 项目的 Linope 工具。关于 Pi 项目，可以查看：https://github.com/earendil-works/pi.git";

const model = {
  id: "linope",
  name: "linope",
  api: "openai-completions",
  provider: "openai",
  baseUrl: "http://127.0.0.1",
  input: ["text"],
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
  reasoning: false,
  contextWindow: 128000,
  maxTokens: 8192,
};

const defaultTools = ["read", "bash", "edit", "write"];

export async function openPiSession({
  cwd = process.cwd(),
  agentDir,
  askModel,
  onProgress,
  openAuthorization,
  waitForRedirect,
}) {
  const note = (text) => {
    if (typeof onProgress === "function" && text) onProgress(String(text));
  };
  const directory = agentDir || getAgentDir();
  mkdirSync(directory, { recursive: true });
  const settings = SettingsManager.create(cwd, directory);
  const loader = new DefaultResourceLoader({
    cwd,
    agentDir: directory,
    settingsManager: settings,
    extensionFactories: piExtensions(openAuthorization || openBrowser),
    appendSystemPrompt: [PREAMBLE],
  });
  await loader.reload();
  const sessionManager = SessionManager.inMemory(cwd);
  const modelRuntime = runtimeThatDoesNotCallProviders();
  const streamFn = (_model, context) => modelStream(askModel, context, note);
  const names = process.platform === "win32" ? [...defaultTools, "powershell"] : [...defaultTools];
  const agent = new Agent({
    initialState: {
      systemPrompt: "",
      model,
      thinkingLevel: "off",
      tools: [],
      messages: [],
    },
    convertToLlm,
    streamFn,
    sessionId: sessionManager.getSessionId(),
  });
  const pi = new AgentSession({
    agent,
    sessionManager,
    settingsManager: settings,
    cwd,
    resourceLoader: loader,
    modelRuntime,
    initialActiveToolNames: names,
    usesDefaultTools: true,
    defaultToolModifiers: process.platform === "win32" ? ["+powershell"] : [],
  });
  const logins = new Set();
  pi.subscribe((event) => note(progressText(event)));
  await pi.bindExtensions({
    mode: "print",
    uiContext: printUi(note, logins, waitForRedirect),
  });
  if (oauthConfigured(cwd, directory)) {
    const deadline = Date.now() + 10000;
    while (logins.size === 0 && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
  }
  for (const name of logins) await pi.prompt(`/mcp login ${name}`);
  return {
    async prompt(question) {
      await pi.prompt(String(question ?? ""));
      return finalText(pi.messages);
    },
    get messages() {
      return pi.messages;
    },
    async close() {
      const runner = pi._extensionRunner;
      if (runner?.hasHandlers?.("session_shutdown")) {
        await runner.emit({ type: "session_shutdown", reason: "quit" }).catch(() => undefined);
      }
      pi.dispose();
    },
  };
}

export async function runWithPiTools(options) {
  const session =
    options.session ||
    (await openPiSession({ ...options, agentDir: options.agentDir || isolatedAgentDir() }));
  try {
    return await session.prompt(options.question);
  } finally {
    if (!options.session) await session.close();
  }
}

function piExtensions(openUrl) {
  return [
    { name: "codemode", factory: createCodemodeExtension(), builtin: true, replaceable: true },
    { name: "tool-search", factory: createToolSearchExtension(), builtin: true, replaceable: true },
    { name: "mcp", factory: createMcpExtension({ openUrl }), builtin: true, replaceable: true },
  ];
}

function openBrowser(target) {
  const [command, args] =
    process.platform === "darwin"
      ? ["open", [target]]
      : process.platform === "win32"
        ? ["rundll32", ["url.dll,FileProtocolHandler", target]]
        : ["xdg-open", [target]];
  spawn(command, args, {
    stdio: "ignore",
    detached: true,
    cwd: process.platform === "win32" ? undefined : "/",
  })
    .on("error", () => {})
    .unref();
}

function runtimeThatDoesNotCallProviders() {
  return {
    hasConfiguredAuth() {
      return true;
    },
    async checkAuth() {
      return { ok: true };
    },
    isUsingOAuth() {
      return false;
    },
    async getAuth() {
      return undefined;
    },
    getModel() {
      return undefined;
    },
    getPhysicalModel() {
      return undefined;
    },
    getModels() {
      return [];
    },
    getAvailableSnapshot() {
      return [];
    },
    getError() {
      return undefined;
    },
    async refresh() {
      return { models: [] };
    },
    async resolveModel(selected, _messages, options) {
      return { model: selected, thinkingLevel: options?.thinkingLevel };
    },
  };
}

function printUi(note, logins, waitForRedirect) {
  const unused = () => {};
  return {
    notify(message) {
      const text = String(message || "");
      note(text);
      for (const found of text.matchAll(/\/mcp login (\S+)/g)) logins.add(found[1]);
      for (const found of text.matchAll(/^\s*(\S+): needs sign-in\b/gm)) logins.add(found[1]);
    },
    async select(_title, options) {
      return options?.[0];
    },
    async confirm() {
      return true;
    },
    input(_title, _placeholder, opts) {
      return redirectLine(opts?.signal, waitForRedirect);
    },
    onTerminalInput() {
      return unused;
    },
    setStatus(_key, text) {
      if (text) note(String(text));
    },
    setWorkingMessage: unused,
    setWorkingVisible: unused,
    setWorkingIndicator: unused,
    setHiddenThinkingLabel: unused,
    setWidget: unused,
    setFooter: unused,
    setHeader: unused,
    setTitle: unused,
    async custom() {
      return undefined;
    },
    pasteToEditor: unused,
    setEditorText: unused,
    getEditorText() {
      return "";
    },
    async editor() {
      return undefined;
    },
    addAutocompleteProvider: unused,
    setEditorComponent: unused,
  };
}

function redirectLine(signal, waitForRedirect) {
  if (waitForRedirect) return waitForRedirect(signal);
  if (signal?.aborted) return Promise.resolve(undefined);
  return new Promise((resolve) => {
    signal?.addEventListener("abort", () => resolve(undefined), { once: true });
  });
}

function oauthConfigured(cwd, agentDir) {
  for (const path of [join(agentDir, "mcp.json"), join(cwd, ".pi", "mcp.json")]) {
    if (!existsSync(path)) continue;
    try {
      const parsed = JSON.parse(readFileSync(path, "utf8"));
      for (const server of Object.values(parsed.mcpServers || {})) {
        if (server && typeof server === "object" && server.url && !server.auth) return true;
      }
    } catch {
      return true;
    }
  }
  return false;
}

async function modelStream(askModel, context, note) {
  note("正在问模型");
  const spoken = await askModel(modelMessages(context.messages), modelTools(context.messages));
  const stream = new AssistantMessageEventStream();
  stream.push({
    type: "done",
    reason: spoken.toolCalls?.length ? "toolUse" : "stop",
    message: assistantMessage(spoken),
  });
  return stream;
}

function progressText(event) {
  if (!event) return "";
  if (event.type === "tool_execution_start") {
    const name = String(event.toolName || "").trim();
    if (!name) return "";
    const detail = argumentText(event.args);
    return detail ? `${name} ${detail}` : name;
  }
  if (event.type === "tool_execution_end" && event.isError) {
    const name = String(event.toolName || "").trim();
    return name ? `${name} 失败` : "";
  }
  return "";
}

function argumentText(args) {
  if (!args || typeof args !== "object") return "";
  for (const key of ["path", "file_path", "command", "pattern", "query", "url"]) {
    const value = args[key];
    if (typeof value === "string" && value.trim()) return clip(value);
  }
  return "";
}

function clip(text) {
  const one = String(text).trim().replace(/\s+/g, " ");
  return one.length > 80 ? `${one.slice(0, 79)}…` : one;
}

function modelMessages(messages) {
  const out = [];
  const system = getCurrentSystemMessage(messages);
  if (system) out.push({ role: "system", content: getSystemMessageText(system) });
  for (const message of messages) {
    if (message.role === "user") {
      out.push({ role: "user", content: userContent(message.content) });
    } else if (message.role === "assistant") {
      out.push({ role: "assistant", content: assistantBlocks(message.content) });
    } else if (message.role === "toolResult") {
      out.push({
        role: "tool",
        name: message.toolName,
        tool_call_id: message.toolCallId,
        content: textOf(message.content),
      });
    }
  }
  return out;
}

function userContent(content) {
  if (typeof content === "string") return content;
  const images = (content || []).filter((block) => block && block.type === "image");
  const text = textOf(content);
  if (images.length === 0) return text;
  return [{ type: "text", text }, ...images];
}

function modelTools(messages) {
  return getCurrentTools(messages).map((tool) => ({
    name: tool.name,
    description: String(tool.description || ""),
    parameters: JSON.parse(JSON.stringify(tool.parameters)),
  }));
}

function assistantBlocks(content) {
  const blocks = [];
  for (const block of content || []) {
    if (block.type === "text" && block.text) blocks.push({ type: "text", text: block.text });
    if (block.type === "toolCall") {
      blocks.push({
        type: "tool-call",
        id: block.id,
        name: block.name,
        arguments: block.arguments,
      });
    }
  }
  return blocks;
}

function assistantMessage(spoken) {
  const content = [];
  if (spoken.text) content.push({ type: "text", text: String(spoken.text) });
  for (const call of spoken.toolCalls || []) {
    content.push({
      type: "toolCall",
      id: String(call.id || `call-${content.length + 1}`),
      name: String(call.name),
      arguments: call.arguments && typeof call.arguments === "object" ? call.arguments : {},
    });
  }
  return {
    role: "assistant",
    content,
    api: model.api,
    provider: model.provider,
    model: model.id,
    usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    stopReason: content.some((block) => block.type === "toolCall") ? "toolUse" : "stop",
    timestamp: Date.now(),
  };
}

function finalText(messages) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role !== "assistant") continue;
    const text = textOf(message.content);
    return text || String(message.errorMessage || "");
  }
  return "";
}

function textOf(content) {
  if (typeof content === "string") return content;
  return (content || [])
    .filter((block) => block && block.type === "text" && block.text)
    .map((block) => String(block.text))
    .join("\n");
}

export function parseModelTurn(raw) {
  const text = typeof raw === "string" ? raw.trim() : "";
  const data = raw && typeof raw === "object" ? raw : null;
  if (!data && !text.startsWith("{")) return { text, toolCalls: [] };
  try {
    const parsed = data || JSON.parse(text);
    if (!parsed || parsed.type !== "model_turn" || !Array.isArray(parsed.blocks)) {
      return { text, toolCalls: [] };
    }
    const prose = parsed.blocks
      .filter((block) => block && block.type === "text" && block.text)
      .map((block) => String(block.text))
      .join("\n");
    const toolCalls = parsed.blocks
      .filter((block) => block && block.type === "tool-call" && block.name)
      .map((block, index) => ({
        id: String(block.id || `call-${index + 1}`),
        name: String(block.name),
        arguments: parseArguments(block.arguments),
      }));
    return { text: prose, toolCalls };
  } catch {
    return { text, toolCalls: [] };
  }
}

function parseArguments(value) {
  if (value == null || value === "") return {};
  if (typeof value === "object") return value;
  try {
    const parsed = JSON.parse(String(value));
    return parsed && typeof parsed === "object" ? parsed : { value: parsed };
  } catch {
    return { value: String(value) };
  }
}

export function isolatedAgentDir() {
  return join(tmpdir(), `linope-pi-agent-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}
