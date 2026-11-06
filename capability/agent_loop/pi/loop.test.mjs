import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { isolatedAgentDir, openPiSession, parseModelTurn, runWithPiTools } from "./loop.mjs";

test("a read call uses Pi's path argument and does not start tools.read", async () => {
  const cwd = mkdtempSync(join(tmpdir(), "linope-pi-"));
  writeFileSync(join(cwd, "note.txt"), "hello from pi\n", "utf8");
  writeFileSync(join(cwd, "AGENTS.md"), "Project note from the agents file.\n", "utf8");
  mkdirSync(join(cwd, ".pi", "skills", "greet"), { recursive: true });
  writeFileSync(
    join(cwd, ".pi", "skills", "greet", "SKILL.md"),
    "---\nname: greet\ndescription: Greet from the linope skill fixture.\n---\nSay hello.\n",
    "utf8",
  );
  const requests = [];
  let step = 0;

  const progress = [];
  const answer = await runWithPiTools({
    question: "read note.txt",
    cwd,
    onProgress: (text) => progress.push(text),
    askModel: async (messages, tools) => {
      requests.push({ messages, tools });
      const read = tools.find((tool) => tool.name === "read");
      assert.equal(read.parameters.properties.path.type, "string");
      assert.equal(read.parameters.required.includes("path"), true);
      if (step === 0) {
        step += 1;
        return { text: "", toolCalls: [{ id: "call-1", name: "read", arguments: { path: "note.txt" } }] };
      }
      const result = messages.find((message) => message.role === "tool");
      assert.match(result.content, /hello from pi/);
      return { text: "The file says hello from pi.", toolCalls: [] };
    },
  });

  assert.equal(answer, "The file says hello from pi.");
  assert.deepEqual(progress, ["正在问模型", "read note.txt", "正在问模型"]);
  const first = JSON.stringify(requests[0]);
  assert.match(first, /我是使用了 Pi 项目的 Linope 工具/);
  assert.match(first, /Use read to examine files instead of cat or sed/);
  assert.match(first, /Project note from the agents file/);
  assert.match(first, /Greet from the linope skill fixture/);
  assert.equal(first.includes("process start tools.read"), false);
  assert.equal(first.includes("file_path"), false);
});

test("a model turn keeps the tool call arguments", () => {
  const spoken = parseModelTurn(
    JSON.stringify({
      type: "model_turn",
      blocks: [
        { type: "tool-call", id: "call-1", name: "read", arguments: { path: "note.txt" } },
      ],
    }),
  );
  assert.equal(spoken.toolCalls[0].name, "read");
  assert.equal(spoken.toolCalls[0].arguments.path, "note.txt");
});

test("a second question sees the first turn", async () => {
  const cwd = mkdtempSync(join(tmpdir(), "linope-pi-"));
  writeFileSync(join(cwd, "note.txt"), "hello from pi\n", "utf8");
  const requests = [];
  let step = 0;
  const session = await openPiSession({
    cwd,
    agentDir: isolatedAgentDir(),
    askModel: async (messages, tools) => {
      requests.push({ messages, tools });
      if (step === 0) {
        step += 1;
        return { text: "", toolCalls: [{ id: "call-1", name: "read", arguments: { path: "note.txt" } }] };
      }
      if (step === 1) {
        step += 1;
        return { text: "The file says hello from pi.", toolCalls: [] };
      }
      const remembered = JSON.stringify(messages);
      assert.match(remembered, /hello from pi/);
      return { text: "Still hello from pi.", toolCalls: [] };
    },
  });
  try {
    assert.equal(await session.prompt("read note.txt"), "The file says hello from pi.");
    assert.equal(await session.prompt("what did it say"), "Still hello from pi.");
    assert.equal(requests.length, 3);
  } finally {
    await session.close();
  }
});

test("a direct stdio MCP tool runs inside Pi", async () => {
  const cwd = mkdtempSync(join(tmpdir(), "linope-pi-"));
  const server = join(cwd, "mcp-server.mjs");
  writeFileSync(
    server,
    [
      "import { createInterface } from 'node:readline';",
      "const incoming = createInterface({ input: process.stdin });",
      "const send = (value) => process.stdout.write(JSON.stringify(value) + '\\n');",
      "incoming.on('line', (line) => {",
      "  if (!line.trim()) return;",
      "  const message = JSON.parse(line);",
      "  if (message.method === 'initialize') {",
      "    send({ jsonrpc: '2.0', id: message.id, result: { protocolVersion: '2025-11-25', capabilities: { tools: {} }, serverInfo: { name: 'fixture', version: '0' } } });",
      "    return;",
      "  }",
      "  if (message.method === 'tools/list') {",
      "    send({ jsonrpc: '2.0', id: message.id, result: { tools: [{ name: 'echo', description: 'Echo text', inputSchema: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'] } }] } });",
      "    return;",
      "  }",
      "  if (message.method === 'tools/call') {",
      "    send({ jsonrpc: '2.0', id: message.id, result: { content: [{ type: 'text', text: 'echo:' + String(message.params.arguments.text) }] } });",
      "    return;",
      "  }",
      "  if (message.id !== undefined) send({ jsonrpc: '2.0', id: message.id, result: {} });",
      "});",
    ].join("\n"),
    "utf8",
  );
  mkdirSync(join(cwd, ".pi"), { recursive: true });
  writeFileSync(
    join(cwd, ".pi", "mcp.json"),
    JSON.stringify({
      mcpServers: {
        fixture: { command: process.execPath, args: [server], exposure: "direct" },
      },
    }),
    "utf8",
  );
  let step = 0;
  const session = await openPiSession({
    cwd,
    agentDir: isolatedAgentDir(),
    askModel: async (_messages, tools) => {
      const echo = tools.find((tool) => tool.name === "mcp__fixture__echo");
      assert.ok(echo);
      if (step === 0) {
        step += 1;
        return { text: "", toolCalls: [{ id: "call-1", name: "mcp__fixture__echo", arguments: { text: "from-mcp" } }] };
      }
      return { text: "The tool echoed from-mcp.", toolCalls: [] };
    },
  });
  try {
    const answer = await session.prompt("echo something");
    assert.equal(answer, "The tool echoed from-mcp.");
    assert.equal(step, 1);
  } finally {
    await session.close();
  }
});

test("an OAuth callback completes without opening a browser", async () => {
  const cwd = mkdtempSync(join(tmpdir(), "linope-pi-"));
  const agentDir = isolatedAgentDir();
  const gate = await listen((request, response, serverOrigin) => oauthAndMcp(request, response, serverOrigin));
  const origin = gate.origin;
  mkdirSync(join(cwd, ".pi"), { recursive: true });
  writeFileSync(
    join(cwd, ".pi", "mcp.json"),
    JSON.stringify({
      mcpServers: {
        gate: {
          url: `${origin}/mcp`,
          exposure: "direct",
          oauth: { clientRegistration: "dcr" },
        },
      },
    }),
    "utf8",
  );
  const progress = [];
  const opened = [];
  const session = await openPiSession({
    cwd,
    agentDir,
    onProgress: (text) => progress.push(text),
    openAuthorization: async (url) => {
      opened.push(url);
      const response = await fetch(url, { redirect: "manual" });
      const location = response.headers.get("location");
      assert.ok(location);
      await fetch(location);
    },
    askModel: async () => ({ text: "signed in", toolCalls: [] }),
  });
  try {
    assert.equal(opened.length, 1, progress.join("\n"));
    assert.ok(progress.some((text) => text.includes(opened[0])));
    assert.ok(progress.some((text) => text.startsWith("Signed in to MCP server")));
    assert.equal(await session.prompt("hello"), "signed in");
  } finally {
    await session.close();
    await gate.close();
  }
});

test("the process source does not call a provider or open kernel memory", () => {
  const source = readFileSync(new URL("./main.mjs", import.meta.url), "utf8");
  assert.equal(source.includes("fetch("), false);
  assert.equal(source.includes("kernel/"), false);
  assert.equal(source.includes("from \"kernel"), false);
  assert.equal(source.includes("workspace-write"), false);
  assert.equal(source.includes("danger-full-access"), false);
  assert.equal(source.includes("system_02_tools"), false);
  assert.equal(source.includes("process start tools.read"), false);
});

function listen(handler) {
  const server = createServer((request, response) => {
    const address = server.address();
    const origin = `http://127.0.0.1:${address.port}`;
    Promise.resolve(handler(request, response, origin)).catch((error) => {
      response.writeHead(500).end(String(error.message || error));
    });
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () =>
      resolve({
        origin: `http://127.0.0.1:${server.address().port}`,
        close: () =>
          new Promise((done, fail) => {
            server.close((error) => (error ? fail(error) : done()));
          }),
      }),
    );
  });
}

function readBody(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    request.on("error", reject);
  });
}

function sendJson(response, status, body, headers = {}) {
  response.writeHead(status, { "content-type": "application/json", ...headers }).end(JSON.stringify(body));
}

const challenges = new Map();
let accessToken = "";

async function oauthAndMcp(request, response, origin) {
  const url = new URL(request.url || "/", origin);
  if (url.pathname === "/.well-known/oauth-protected-resource/mcp") {
    sendJson(response, 200, { resource: `${origin}/mcp`, authorization_servers: [origin] });
    return;
  }
  if (url.pathname === "/.well-known/oauth-authorization-server") {
    sendJson(response, 200, {
      issuer: origin,
      authorization_endpoint: `${origin}/authorize`,
      token_endpoint: `${origin}/token`,
      registration_endpoint: `${origin}/register`,
      response_types_supported: ["code"],
      code_challenge_methods_supported: ["S256"],
      token_endpoint_auth_methods_supported: ["none"],
    });
    return;
  }
  if (url.pathname === "/register") {
    const metadata = JSON.parse(await readBody(request));
    sendJson(response, 201, { ...metadata, client_id: "client-1" });
    return;
  }
  if (url.pathname === "/authorize") {
    const code = "code-1";
    challenges.set(code, url.searchParams.get("code_challenge") || "");
    const redirect = new URL(url.searchParams.get("redirect_uri") || "");
    redirect.searchParams.set("code", code);
    redirect.searchParams.set("state", url.searchParams.get("state") || "");
    response.writeHead(302, { location: redirect.href }).end();
    return;
  }
  if (url.pathname === "/token") {
    const params = new URLSearchParams(await readBody(request));
    const code = params.get("code") || "";
    const verifier = createHash("sha256").update(params.get("code_verifier") || "").digest("base64url");
    if (challenges.get(code) !== verifier) {
      sendJson(response, 400, { error: "invalid_grant" });
      return;
    }
    accessToken = "access-1";
    sendJson(response, 200, { access_token: accessToken, refresh_token: "refresh-1", token_type: "Bearer" });
    return;
  }
  if (url.pathname === "/mcp") {
    const header = String(request.headers.authorization || "");
    if (header !== `Bearer ${accessToken}` || !accessToken) {
      response.writeHead(401, {
        "www-authenticate": `Bearer resource_metadata="${origin}/.well-known/oauth-protected-resource/mcp"`,
        "content-type": "application/json",
      });
      response.end(JSON.stringify({ error: "unauthorized" }));
      return;
    }
    if (request.method === "GET") {
      response.writeHead(405).end();
      return;
    }
    if (request.method === "DELETE") {
      response.writeHead(200).end();
      return;
    }
    const message = JSON.parse(await readBody(request));
    if (!("id" in message)) {
      response.writeHead(202).end();
      return;
    }
    if (message.method === "initialize") {
      sendJson(
        response,
        200,
        {
          jsonrpc: "2.0",
          id: message.id,
          result: {
            protocolVersion: "2025-11-25",
            capabilities: { tools: {} },
            serverInfo: { name: "gate", version: "0" },
          },
        },
        { "mcp-session-id": "session-1" },
      );
      return;
    }
    if (message.method === "tools/list") {
      sendJson(response, 200, {
        jsonrpc: "2.0",
        id: message.id,
        result: { tools: [{ name: "ping", description: "Ping", inputSchema: { type: "object" } }] },
      });
      return;
    }
    sendJson(response, 200, { jsonrpc: "2.0", id: message.id, result: {} });
    return;
  }
  response.writeHead(404).end();
}
