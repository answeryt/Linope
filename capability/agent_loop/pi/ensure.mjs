/**
 * Put Pi's published packages where this process can import them.
 * A checkout that already has node_modules is used as it is. A read-only
 * install receives a copy under the user's home directory.
 */

import { spawn } from "node:child_process";
import { access, constants, copyFile, mkdir, readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const PACKAGE = join("node_modules", "@earendil-works", "pi-coding-agent", "package.json");
const COPIED = ["package.json", "package-lock.json", "loop.mjs"];

export async function ensureLoop(moduleUrl, options = {}) {
  const sourceDir = dirname(fileURLToPath(moduleUrl));
  const home = options.home || join(homedir(), ".linope", "agent-loop");
  const run = options.run || npmInstall;
  const writable = options.writable ?? (await canWrite(sourceDir));
  return placeLoop(sourceDir, { home, run, writable });
}

export async function placeLoop(sourceDir, { home, run, writable }) {
  if (await hasPackages(sourceDir)) return join(sourceDir, "loop.mjs");
  const dest = writable ? sourceDir : home;
  if (dest === sourceDir) {
    await run(dest);
  } else {
    const installed = await hasPackages(dest);
    const current = await sameFile(join(sourceDir, "package-lock.json"), join(dest, "package-lock.json"));
    if (!installed || !current) {
      await copyRuntime(sourceDir, dest);
      await run(dest);
    } else {
      await mkdir(dest, { recursive: true });
      await copyFile(join(sourceDir, "loop.mjs"), join(dest, "loop.mjs"));
    }
  }
  if (!(await hasPackages(dest))) {
    throw new Error("Pi's packages are still missing after npm install");
  }
  return join(dest, "loop.mjs");
}

async function hasPackages(dir) {
  try {
    await access(join(dir, PACKAGE));
    return true;
  } catch {
    return false;
  }
}

async function canWrite(dir) {
  try {
    await access(dir, constants.W_OK);
    return true;
  } catch {
    return false;
  }
}

async function copyRuntime(sourceDir, dest) {
  await mkdir(dest, { recursive: true });
  for (const name of COPIED) {
    await copyFile(join(sourceDir, name), join(dest, name));
  }
}

async function sameFile(left, right) {
  try {
    return (await readFile(left)).equals(await readFile(right));
  } catch {
    return false;
  }
}

function npmInstall(cwd) {
  const npm = process.platform === "win32" ? "npm.cmd" : "npm";
  const lock = join(cwd, "package-lock.json");
  return access(lock).then(
    () => runNpm(npm, ["ci", "--omit=dev"], cwd),
    () => runNpm(npm, ["install", "--omit=dev"], cwd),
  );
}

function runNpm(npm, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(npm, args, {
      cwd,
      shell: process.platform === "win32",
      stdio: ["ignore", "ignore", "pipe"],
      windowsHide: true,
    });
    const errors = [];
    child.stderr?.on("data", (chunk) => errors.push(chunk));
    child.on("error", () => {
      reject(new Error("npm was not found. Install Node.js, then start this process again."));
    });
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      const detail = Buffer.concat(errors).toString("utf8").trim();
      reject(new Error(detail || `npm exited with status ${code}`));
    });
  });
}
