const { spawn } = require("node:child_process");
const { createInterface } = require("node:readline");

const LOCAL_SEQUENCE = Number.MAX_SAFE_INTEGER;

function pythonCommand() {
  return process.env.LINOPE_PYTHON?.trim() || process.env.PYTHON?.trim() || "python";
}

function recordOf(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function parseKernelEvent(line) {
  const payload = recordOf(JSON.parse(line));
  if (!payload || payload.version !== 1 || typeof payload.kind !== "string") {
    throw new Error("Unsupported kernel event");
  }

  if (!Number.isInteger(payload.seq) || payload.seq < 1) {
    throw new Error("Kernel event has an invalid sequence");
  }

  const data = recordOf(payload.data);
  if (!data) {
    throw new Error("Kernel event has invalid data");
  }

  const event = {
    data,
    kind: payload.kind,
    seq: payload.seq,
    version: 1,
  };

  for (const [key, type] of [
    ["request_id", "string"],
    ["turn_id", "string"],
  ]) {
    if (payload[key] !== undefined) {
      if (typeof payload[key] !== type) {
        throw new Error(`Kernel event has an invalid ${key}`);
      }
      event[key] = payload[key];
    }
  }

  if (payload.pid !== undefined) {
    if (!Number.isInteger(payload.pid) || payload.pid <= 0) {
      throw new Error("Kernel event has an invalid pid");
    }
    event.pid = payload.pid;
  }

  return event;
}

class KernelSession {
  constructor({ cwd, onEvent }) {
    this.onEvent = onEvent;
    this.stderr = "";
    this.stopped = false;
    this.requestSequence = 0;
    this.proc = spawn(
      pythonCommand(),
      ["-u", "-m", "connection.gateway"],
      {
        cwd,
        env: {
          ...process.env,
          PYTHONIOENCODING: "utf-8",
          PYTHONUTF8: "1",
        },
        stdio: ["pipe", "pipe", "pipe"],
        windowsHide: true,
      },
    );

    createInterface({ input: this.proc.stdout }).on("line", (line) => {
      if (!line.trim()) {
        return;
      }
      try {
        this.emit(parseKernelEvent(line));
      } catch (error) {
        this.emit({
          data: {
            line,
            message: error instanceof Error ? error.message : String(error),
          },
          kind: "protocol.error",
          seq: LOCAL_SEQUENCE,
          version: 1,
        });
      }
    });

    this.proc.stderr.setEncoding("utf8");
    this.proc.stderr.on("data", (chunk) => {
      this.stderr += chunk;
      if (this.stderr.includes("\n")) {
        this.emitStderr();
      }
    });

    this.proc.on("error", (error) => {
      this.emit({
        data: { message: error.message, source: "process" },
        kind: "diagnostic",
        seq: LOCAL_SEQUENCE,
        version: 1,
      });
    });

    this.proc.on("close", () => {
      this.emitStderr();
      this.emit({
        data: { reason: "process_closed" },
        kind: "session.closed",
        seq: LOCAL_SEQUENCE,
        version: 1,
      });
    });
  }

  emit(event) {
    this.onEvent(event);
  }

  emitStderr() {
    const text = this.stderr.trim();
    this.stderr = "";
    if (text) {
      this.emit({
        data: { message: text, source: "stderr" },
        kind: "diagnostic",
        seq: LOCAL_SEQUENCE,
        version: 1,
      });
    }
  }

  request(action, payload, requestId) {
    if (
      this.proc.exitCode !== null ||
      this.proc.killed ||
      !this.proc.stdin.writable
    ) {
      this.emit({
        data: { message: "The clerk has left" },
        kind: "protocol.error",
        seq: LOCAL_SEQUENCE,
        version: 1,
      });
      return undefined;
    }

    const id = requestId || `request-${++this.requestSequence}`;
    this.proc.stdin.write(
      `${JSON.stringify({
        action,
        payload,
        request_id: id,
        version: 1,
      })}\n`,
    );
    return id;
  }

  send(text) {
    this.request("command.execute", { command: String(text).trim() });
  }

  stop() {
    if (this.stopped) {
      return;
    }
    this.stopped = true;
    if (this.proc.exitCode !== null || this.proc.killed) {
      return;
    }
    try {
      this.request("command.execute", { command: "exit" });
    } catch {
      this.proc.kill();
    }
  }
}

module.exports = { KernelSession };
