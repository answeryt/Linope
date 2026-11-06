/**
 * One capability process. Pi runs the tool loop. This file writes the same
 * command lines a person can type when it asks the model.
 */

import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";

import { ensureLoop } from "./ensure.mjs";

let openPiSession;
let parseModelTurn;

const lines = [];
const waiters = [];
const living = new Map();
let selfPid = 0;
let modelName = "model.openai_chat_model";
let redirectWaiter = null;
let sessionPromise;

const incoming = createInterface({ input: process.stdin, crlfDelay: Infinity });
incoming.on("line", (line) => {
  const pasted = callbackText(line);
  if (redirectWaiter && pasted) {
    const waiter = redirectWaiter;
    redirectWaiter = null;
    waiter(pasted);
    return;
  }
  const waiter = waiters.shift();
  if (waiter) waiter(line);
  else lines.push(line);
});

function nextLine() {
  if (lines.length > 0) return Promise.resolve(lines.shift());
  return new Promise((resolve) => waiters.push(resolve));
}

function write(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

async function submit(line) {
  write({ event: "command", line });
  const raw = await nextLine();
  let reply;
  try {
    reply = JSON.parse(raw);
  } catch {
    throw new Error("The kernel returned a broken command result");
  }
  if (!reply || reply.event !== "command_result") {
    throw new Error("The kernel returned a broken command result");
  }
  if (reply.error) throw new Error(String(reply.error));
  return String(reply.result || "");
}

function remember(output) {
  for (const line of String(output || "").split(/\r?\n/)) {
    const found = /pid=(\d+)\s+capability=(\S+)/.exec(line.trim());
    if (found) living.set(found[2], found[1]);
  }
}

async function ensure(name, extra = "") {
  const known = living.get(name);
  if (known) return known;
  const line = extra ? `process start ${name} ${extra}` : `process start ${name}`;
  const output = await submit(line);
  remember(output);
  const pid = living.get(name);
  if (!pid) throw new Error(output || `Could not start ${name}`);
  return pid;
}

function callbackText(line) {
  const raw = String(line ?? "").trim();
  if (/^https?:\/\//.test(raw) && raw.includes("code=")) return raw;
  try {
    const message = JSON.parse(raw);
    const body = typeof message.body === "string" ? message.body.trim() : "";
    if (/^https?:\/\//.test(body) && body.includes("code=")) return body;
  } catch {
    return "";
  }
  return "";
}

function waitForRedirect(signal) {
  if (signal?.aborted) return Promise.resolve(undefined);
  for (let index = 0; index < lines.length; index += 1) {
    const pasted = callbackText(lines[index]);
    if (!pasted) continue;
    lines.splice(index, 1);
    return Promise.resolve(pasted);
  }
  return new Promise((resolve) => {
    const finish = (value) => {
      if (redirectWaiter === finish) redirectWaiter = null;
      signal?.removeEventListener("abort", onAbort);
      resolve(value);
    };
    const onAbort = () => finish(undefined);
    signal?.addEventListener("abort", onAbort, { once: true });
    redirectWaiter = finish;
  });
}

function session() {
  sessionPromise ??= openPiSession({
    cwd: process.cwd(),
    onProgress: (text) => write({ type: "status", text: String(text) }),
    waitForRedirect,
    askModel: async (messages, tools) => {
      const pid = await ensure(modelName, "--with memory=chat");
      const body = JSON.stringify({ messages, tools });
      return parseModelTurn(await submit(`load message ${pid} -- ${body}`));
    },
  });
  return sessionPromise;
}

async function answer(question) {
  await refresh();
  const pasted = callbackText(JSON.stringify({ body: question }));
  if (redirectWaiter && pasted) {
    const waiter = redirectWaiter;
    redirectWaiter = null;
    waiter(pasted);
    return "";
  }
  return (await session()).prompt(question);
}

async function refresh() {
  remember(await submit("list"));
}

async function handle(message) {
  if (message.operation === "ping") {
    write({
      event: "pong",
      pid: selfPid,
      seq: message.seq,
      channel: message.channel || "",
    });
    return;
  }
  if (message.operation !== "load" || message.kind !== "message") {
    write({ event: "error", error: "This process only accepts load message" });
    return;
  }
  const body = message.body;
  const question = typeof body === "string" ? body : JSON.stringify(body ?? "");
  write({ event: "result", result: await answer(question) });
}

async function main() {
  const startup = JSON.parse(await nextLine());
  const activation = startup.activation;
  if (!activation || typeof activation !== "object") {
    write({ event: "error", error: "The startup message does not name this capability" });
    return;
  }
  selfPid = Number(activation.pid || 0);
  const settings = activation.resource_context?.settings || {};
  if (settings.model) modelName = String(settings.model);
  write({ event: "ready", pid: selfPid });
  try {
    const loopPath = await ensureLoop(import.meta.url);
    const loop = await import(pathToFileURL(loopPath).href);
    openPiSession = loop.openPiSession;
    parseModelTurn = loop.parseModelTurn;
  } catch (error) {
    write({ event: "error", error: String(error.message || error) });
    process.exitCode = 1;
    return;
  }
  session().catch((error) => {
    write({ event: "error", error: String(error.message || error) });
  });
  for (;;) {
    const raw = await nextLine();
    if (raw == null) return;
    let message;
    try {
      message = JSON.parse(raw);
    } catch (error) {
      write({ event: "error", error: String(error.message || error) });
      continue;
    }
    try {
      await handle(message);
    } catch (error) {
      write({ event: "error", error: String(error.message || error) });
    }
  }
}

main().catch((error) => {
  write({ event: "error", error: String(error.message || error) });
  process.exitCode = 1;
});
