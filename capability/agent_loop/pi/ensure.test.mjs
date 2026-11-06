import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { placeLoop } from "./ensure.mjs";

async function tree() {
  const root = await mkdtemp(join(tmpdir(), "linope-ensure-"));
  const source = join(root, "source");
  const home = join(root, "home");
  await mkdir(source, { recursive: true });
  await writeFile(join(source, "package.json"), "{}\n");
  await writeFile(join(source, "package-lock.json"), "{\"lock\":1}\n");
  await writeFile(join(source, "loop.mjs"), "export const marker = 1;\n");
  return { source, home };
}

async function markInstalled(dir) {
  const pkg = join(dir, "node_modules", "@earendil-works", "pi-coding-agent");
  await mkdir(pkg, { recursive: true });
  await writeFile(join(pkg, "package.json"), "{}\n");
}

test("an existing install is used without npm", async () => {
  const { source, home } = await tree();
  await markInstalled(source);
  let called = false;
  const path = await placeLoop(source, {
    home,
    writable: true,
    run: async () => {
      called = true;
    },
  });
  assert.equal(path, join(source, "loop.mjs"));
  assert.equal(called, false);
});

test("a writable directory without packages runs npm there", async () => {
  const { source, home } = await tree();
  const installed = [];
  const path = await placeLoop(source, {
    home,
    writable: true,
    run: async (dir) => {
      installed.push(dir);
      await markInstalled(dir);
    },
  });
  assert.deepEqual(installed, [source]);
  assert.equal(path, join(source, "loop.mjs"));
});

test("a read-only directory installs under the home copy", async () => {
  const { source, home } = await tree();
  const installed = [];
  const path = await placeLoop(source, {
    home,
    writable: false,
    run: async (dir) => {
      installed.push(dir);
      await markInstalled(dir);
    },
  });
  assert.deepEqual(installed, [home]);
  assert.equal(path, join(home, "loop.mjs"));
  assert.equal(await readFile(join(home, "loop.mjs"), "utf8"), "export const marker = 1;\n");
});

test("a home install with the same lock only refreshes the script", async () => {
  const { source, home } = await tree();
  await markInstalled(home);
  await writeFile(join(home, "package-lock.json"), await readFile(join(source, "package-lock.json")));
  await writeFile(join(home, "loop.mjs"), "export const marker = 0;\n");
  let called = false;
  const path = await placeLoop(source, {
    home,
    writable: false,
    run: async () => {
      called = true;
    },
  });
  assert.equal(called, false);
  assert.equal(path, join(home, "loop.mjs"));
  assert.equal(await readFile(path, "utf8"), "export const marker = 1;\n");
});
