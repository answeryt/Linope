/**
 * Two tasks on the deepseek-harness loop order.
 *
 * packages/core/agent-loop/src/agent.ts step() finishes the model stream,
 * then runs tools, then asks the model again. This runner keeps that order
 * and does not add a lock around the model call. The harness packages are not
 * installed in this tree, so the requests go through the same recorded proxy
 * instead of importing the workspace.
 */

import { spawn, spawnSync } from "node:child_process"
import { createHash } from "node:crypto"
import { appendFileSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, "..", "..")
const prompt = readFileSync(resolve(here, "prompt.txt"), "utf8").trim()
const toolSchema = JSON.parse(readFileSync(resolve(here, "tools.json"), "utf8"))

function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms)
}

function appendEvent(path, event) {
  mkdirSync(dirname(path), { recursive: true })
  const lock = `${path}.lock`
  for (;;) {
    try {
      writeFileSync(lock, "", { flag: "wx" })
      break
    } catch {
      sleep(10)
    }
  }
  try {
    appendFileSync(path, `${JSON.stringify(event)}\n`)
  } finally {
    unlinkSync(lock)
  }
}

function fingerprint() {
  const hash = (name) => createHash("sha256").update(readFileSync(resolve(here, name))).digest("hex")
  return { prompt: hash("prompt.txt"), tools: hash("tools.json") }
}

function python() {
  return process.env.PYTHON || "python"
}

function tasksFor(group, seconds, nonce) {
  const code = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(repo)})`,
    "from example.utilization.common import tasks_for",
    `print(json.dumps(tasks_for(${JSON.stringify(group)}, ${Number(seconds)}, ${JSON.stringify(nonce)}), default=str))`,
  ].join("\n")
  const result = spawnSync(python(), ["-c", code], { encoding: "utf8" })
  if (result.status !== 0) {
    throw new Error(result.stderr || "Could not build the shared tasks")
  }
  return JSON.parse(result.stdout)
}

function openaiTools() {
  return toolSchema.map((item) => ({
    type: "function",
    function: {
      name: item.name,
      description: item.description,
      parameters: item.parameters,
    },
  }))
}

async function chat(baseUrl, body, taskId) {
  const headers = {
    "content-type": "application/json",
    "x-task-id": taskId,
  }
  if (process.env.OPENAI_API_KEY) {
    headers.authorization = `Bearer ${process.env.OPENAI_API_KEY}`
  }
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/chat/completions`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json()
}

function runTool(args) {
  const result = spawnSync(python(), [
    resolve(here, "slow_read.py"),
    "--path",
    String(args.path || ""),
    "--seconds",
    String(args.seconds ?? 0),
  ], { encoding: "utf8" })
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || "wait_read failed")
  }
  return result.stdout
}

async function oneTask(baseUrl, model, task, logPath) {
  const messages = [
    { role: "system", content: prompt },
    { role: "user", content: task.text },
  ]
  const first = await chat(baseUrl, {
    model,
    temperature: 0,
    messages,
    tools: openaiTools(),
  }, task.id)
  const call = first.choices[0].message.tool_calls[0]
  const args = JSON.parse(call.function.arguments)
  const output = runTool(args)
  messages.push(first.choices[0].message)
  messages.push({ role: "tool", tool_call_id: call.id, content: output })
  await chat(baseUrl, {
    model,
    temperature: 0,
    messages,
    tools: openaiTools(),
  }, task.id)
  appendEvent(logPath, { kind: "task_finished", task: task.id, t: Date.now() / 1000 })
}

function startProxy(logPath, options) {
  const command = [
    resolve(here, "proxy.py"),
    "--log",
    logPath,
  ]
  if (options.mock) {
    command.push("--mock", "--mock-seconds", String(options.mockSeconds))
  } else if (options.upstream) {
    command.push("--upstream", options.upstream)
  }
  const child = spawn(python(), command, { stdio: ["ignore", "pipe", "inherit"] })
  let buffered = ""
  return new Promise((resolvePromise, reject) => {
    child.stdout.on("data", (chunk) => {
      buffered += chunk.toString()
      const line = buffered.split(/\r?\n/, 1)[0]
      if (line) {
        resolvePromise({ child, baseUrl: line.trim() })
      }
    })
    child.on("exit", (code) => reject(new Error(`proxy exited ${code}`)))
  })
}

function parseArgs(argv) {
  const args = {
    group: "",
    nonce: "",
    seconds: 0,
    log: "",
    model: process.env.UTILIZATION_MODEL || "deepseek-flash",
    proxy: "",
    mock: false,
    mockSeconds: 0.05,
    upstream: process.env.UTILIZATION_UPSTREAM || "",
    fingerprint: false,
  }
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index]
    const next = argv[index + 1]
    if (token === "--fingerprint") args.fingerprint = true
    else if (token === "--mock") args.mock = true
    else if (token === "--group") args.group = next
    else if (token === "--nonce") args.nonce = next
    else if (token === "--seconds") args.seconds = Number(next)
    else if (token === "--log") args.log = next
    else if (token === "--model") args.model = next
    else if (token === "--proxy") args.proxy = next
    else if (token === "--upstream") args.upstream = next
    else if (token === "--mock-seconds") args.mockSeconds = Number(next)
    else continue
    if (token.startsWith("--") && token !== "--mock" && token !== "--fingerprint") index += 1
  }
  return args
}

const args = parseArgs(process.argv.slice(2))
if (args.fingerprint) {
  process.stdout.write(`${JSON.stringify(fingerprint())}\n`)
  process.exit(0)
}
if (!args.group || !args.nonce || !args.log) {
  throw new Error("usage: node run_harness.mjs --group mechanism|real --nonce ID --log FILE [--proxy URL]")
}

let owned = null
let baseUrl = args.proxy
if (!baseUrl) {
  owned = await startProxy(args.log, args)
  baseUrl = owned.baseUrl
}
try {
  const { unlinkSync: remove, existsSync } = await import("node:fs")
  if (existsSync(args.log)) remove(args.log)
  appendEvent(args.log, {
    kind: "round",
    arm: "harness",
    group: args.group,
    nonce: args.nonce,
    fingerprint: fingerprint(),
    t: Date.now() / 1000,
  })
  const tasks = tasksFor(args.group, args.seconds, args.nonce)
  appendEvent(args.log, { kind: "tasks_submitted", t: Date.now() / 1000 })
  await Promise.all(tasks.map((task) => oneTask(baseUrl, args.model, task, args.log)))
} finally {
  owned?.child.kill()
}
