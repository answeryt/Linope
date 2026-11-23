import { spawn } from "node:child_process";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const url = "http://127.0.0.1:5173";

function waitForServer() {
  return new Promise((resolve) => {
    const tick = () => {
      const req = http.get(url, (res) => {
        res.resume();
        resolve();
      });
      req.on("error", () => {
        setTimeout(tick, 300);
      });
    };
    tick();
  });
}

const vite = spawn(
  "npm",
  ["exec", "vite", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
  { cwd: root, shell: true, stdio: "inherit" }
);

let electron;

function stop() {
  if (electron && !electron.killed) {
    electron.kill();
  }
  if (!vite.killed) {
    vite.kill();
  }
}

process.on("SIGINT", () => {
  stop();
  process.exit(0);
});

await waitForServer();

electron = spawn("npm", ["exec", "electron", "--", "electron/main.cjs"], {
  cwd: root,
  shell: true,
  stdio: "inherit",
  env: { ...process.env, VITE_DEV_SERVER_URL: url },
});

electron.on("exit", () => {
  stop();
  process.exit(0);
});
