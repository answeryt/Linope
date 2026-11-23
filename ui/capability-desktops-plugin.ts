import { existsSync, readFileSync, readdirSync, type Dirent } from "node:fs";
import path from "node:path";
import type { Plugin } from "vite";

const VIRTUAL_ID = "virtual:capability-desktops";
const RESOLVED_ID = `\0${VIRTUAL_ID}`;
const FILE_PREFIX = "virtual:capability-desktop/";
const SKIP = new Set(["node_modules", "__pycache__", ".git", "dist", ".venv"]);

function findDesktops(directory: string, found: string[] = []): string[] {
  let entries: Dirent[];
  try {
    entries = readdirSync(directory, { withFileTypes: true });
  } catch {
    return found;
  }
  for (const entry of entries) {
    if (SKIP.has(entry.name)) continue;
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      findDesktops(full, found);
      continue;
    }
    if (entry.isFile() && entry.name === "desktop.tsx") found.push(full);
  }
  return found;
}

function capabilityManifest(desktopFile: string): string {
  const directory = path.dirname(desktopFile);
  const candidates = [
    path.join(directory, "linope.json"),
    path.join(directory, "..", "linope.json"),
  ];
  return candidates.find((file) => existsSync(file) && readCapabilityName(file)) ?? "";
}

function capabilityName(desktopFile: string): string {
  const manifest = capabilityManifest(desktopFile);
  return manifest ? readCapabilityName(manifest) : "";
}

function readCapabilityName(file: string): string {
  try {
    const parsed = JSON.parse(readFileSync(file, "utf8")) as { name?: unknown };
    return typeof parsed.name === "string" ? parsed.name.trim() : "";
  } catch {
    return "";
  }
}

function capabilityDesktops(capabilityRoot: string): Plugin {
  const files = () => findDesktops(capabilityRoot).sort();
  return {
    name: "capability-desktops",
    resolveId(id) {
      if (id === VIRTUAL_ID) return RESOLVED_ID;
      if (!id.startsWith(FILE_PREFIX)) return;
      return files()[Number(id.slice(FILE_PREFIX.length))];
    },
    load(id) {
      if (id !== RESOLVED_ID) return null;
      const found = files();
      for (const file of found) {
        this.addWatchFile(file);
        const manifest = capabilityManifest(file);
        if (manifest) this.addWatchFile(manifest);
      }
      const imports = found
        .map((_, index) => `import * as desk${index} from ${JSON.stringify(`${FILE_PREFIX}${index}`)};`)
        .join("\n");
      const entries = found.map((_, index) => `  [desk${index}.appId]: desk${index}.default,`).join("\n");
      const loops = found.flatMap((file, index) => {
        const name = capabilityName(file);
        return name ? [`  [desk${index}.appId]: ${JSON.stringify(name)},`] : [];
      });
      return `${imports}\nexport const desktops = {\n${entries}\n};\nexport const loops = {\n${loops.join("\n")}\n};\n`;
    },
    configureServer(server) {
      server.watcher.add(capabilityRoot);
      const reload = (file: string) => {
        const base = path.basename(file);
        if (base !== "desktop.tsx" && base !== "linope.json") return;
        const mod = server.moduleGraph.getModuleById(RESOLVED_ID);
        if (!mod) return;
        server.moduleGraph.invalidateModule(mod);
        server.ws.send({ type: "full-reload" });
      };
      server.watcher.on("add", reload);
      server.watcher.on("unlink", reload);
      server.watcher.on("change", reload);
    },
  };
}

export { capabilityDesktops };
