import registry from "../../registry.json";

interface RegistryFile {
  name: string;
  source: string;
}

interface RegistryEntry {
  dependencies: string[];
  files: RegistryFile[];
  registryDependencies: string[];
}

interface RegistryItem {
  dependencies?: string[];
  files: { path: string }[];
  name: string;
  registryDependencies?: string[];
}

const RAW = import.meta.glob("/registry/default/**/*.{ts,tsx}", {
  eager: true,
  import: "default",
  query: "?raw",
}) as Record<string, string>;

const entryByName = new Map<string, RegistryEntry>();

for (const item of (registry as { items: RegistryItem[] }).items) {
  entryByName.set(item.name, {
    dependencies: item.dependencies ?? [],
    files: item.files.map((file) => ({
      name: file.path.split("/").pop() ?? file.path,
      source: RAW[`/${file.path}`] ?? "",
    })),
    registryDependencies: (item.registryDependencies ?? []).map((url) =>
      (url.split("/").pop() ?? "").replace(".json", "")
    ),
  });
}

function registryEntry(name: string): RegistryEntry | undefined {
  return entryByName.get(name);
}

export { registryEntry };
export type { RegistryEntry, RegistryFile };
