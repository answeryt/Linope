import { useSyncExternalStore } from "react";
import aurora from "@/desktop/setting/wall_paper/acf1f68032a588cfd85662e1a4c13112.png";
import ice from "@/desktop/setting/wall_paper/mike-hindle-C6AUqGSAsmg-unsplash.jpg";

const STORAGE_KEY = "linope.settings";
const FALLBACK_CONTEXT = 256000;

const CONTEXT_LENGTHS: Record<string, number> = {
  "claude-fable-5-1": 1_000_000,
  "claude-fable-5": 1_000_000,
  "claude-fable": 1_000_000,
  "claude-opus-5": 1_000_000,
  "claude-sonnet-5": 1_000_000,
  "claude-opus-4-8": 1_000_000,
  "claude-opus-4.8": 1_000_000,
  "claude-opus-4-7": 1_000_000,
  "claude-opus-4.7": 1_000_000,
  "claude-opus-4-6": 1_000_000,
  "claude-sonnet-4-6": 1_000_000,
  "claude-opus-4.6": 1_000_000,
  "claude-sonnet-4.6": 1_000_000,
  claude: 200_000,
  "gpt-5.6-luna": 1_050_000,
  "gpt-5.6-terra": 1_050_000,
  "gpt-5.6-sol": 1_050_000,
  "gpt-5.5": 1_050_000,
  "gpt-5.4-nano": 400_000,
  "gpt-5.4-mini": 400_000,
  "gpt-5.4": 1_050_000,
  "gpt-5.3-codex-spark": 128_000,
  "gpt-5.1-chat": 128_000,
  "gpt-5": 400_000,
  "gpt-4.1": 1_047_576,
  "gpt-4": 128_000,
  gemini: 1_048_576,
  "gemma-4": 256_000,
  gemma4: 256_000,
  "gemma-4-31b": 256_000,
  "gemma-3": 131_072,
  gemma: 8_192,
  "deepseek-v4-pro": 1_000_000,
  "deepseek-v4-flash": 1_000_000,
  "deepseek-chat": 1_000_000,
  "deepseek-reasoner": 1_000_000,
  deepseek: 128_000,
  llama: 131_072,
  "qwen3.6-plus": 1_048_576,
  "qwen3.7-plus": 1_048_576,
  "qwen3-coder-plus": 1_000_000,
  "qwen3-coder": 262_144,
  "qwen3-max": 262_144,
  qwen: 131_072,
  "minimax-m3": 1_000_000,
  minimax: 204_800,
  "glm-5.2": 1_048_576,
  glm: 202_752,
  "grok-composer": 200_000,
  "grok-build-latest": 500_000,
  "grok-build": 256_000,
  "grok-code-fast": 256_000,
  "grok-2-vision": 8_192,
  "grok-4-fast": 2_000_000,
  "grok-4.20": 2_000_000,
  "grok-4.5": 500_000,
  "grok-4.3": 1_000_000,
  "grok-4": 256_000,
  "grok-3": 131_072,
  "grok-2": 131_072,
  grok: 131_072,
  "kimi-k3": 1_048_576,
  kimi: 262_144,
  "solar-open2": 262_144,
  "solar-pro3": 131_072,
  "solar-pro2": 65_536,
  "solar-mini": 32_768,
  "hy3-preview": 262_144,
  hy3: 262_144,
  nemotron: 131_072,
  trinity: 262_144,
  elephant: 262_144,
  "qwen/qwen3.5-397b-a17b": 131_072,
  "qwen/qwen3.5-35b-a3b": 131_072,
  "deepseek-ai/deepseek-v3.2": 65_536,
  "moonshotai/kimi-k2.5": 262_144,
  "moonshotai/kimi-k2.6": 262_144,
  "moonshotai/kimi-k2-thinking": 262_144,
  "minimaxai/minimax-m2.5": 204_800,
  "xiaomimimo/mimo-v2-flash": 262_144,
  "mimo-v2-pro": 1_048_576,
  "mimo-v2.5-pro": 1_048_576,
  "mimo-v2.5": 1_048_576,
  "mimo-v2-omni": 262_144,
  "mimo-v2-flash": 262_144,
  "zai-org/glm-5": 202_752,
};

const contextKeys = Object.entries(CONTEXT_LENGTHS).sort((a, b) => b[0].length - a[0].length);

type Reasoning = "" | "low" | "medium" | "high";

type CardDraft = {
  model: string;
  baseUrl: string;
  apiKey: string;
  stream: boolean | null;
  temperature: number | null;
  topP: number | null;
  maxTokens: string;
  thinking: boolean | null;
  reasoning: Reasoning;
  parallelTools: boolean | null;
  parameters: Record<string, string>;
};

type CardId = string;

type CardSpec = {
  id: CardId;
  label: string;
  apiKeyEnv: string;
  openai: boolean;
  draft: CardDraft;
};

type UploadMeta = {
  id: string;
  name: string;
};

type MemoryBackend = "memory" | "local";

type SettingsState = {
  card: CardId;
  drafts: Record<CardId, CardDraft>;
  cores: number;
  memoryBackend: MemoryBackend;
  localPath: string;
  systemPrompt: string;
  wallpaperId: string;
  uploads: UploadMeta[];
};

const CARD_LIST: CardSpec[] = [
  {
    id: "openai_chat",
    label: "OpenAI Chat",
    apiKeyEnv: "OPENAI_API_KEY",
    openai: true,
    draft: {
      model: "",
      baseUrl: "",
      apiKey: "",
      stream: true,
      temperature: null,
      topP: null,
      maxTokens: "",
      thinking: null,
      reasoning: "",
      parallelTools: null,
      parameters: {},
    },
  },
  {
    id: "openai_response",
    label: "OpenAI Response",
    apiKeyEnv: "OPENAI_API_KEY",
    openai: true,
    draft: {
      model: "",
      baseUrl: "",
      apiKey: "",
      stream: true,
      temperature: null,
      topP: null,
      maxTokens: "",
      thinking: null,
      reasoning: "",
      parallelTools: null,
      parameters: {},
    },
  },
  {
    id: "anthropic",
    label: "Anthropic",
    apiKeyEnv: "ANTHROPIC_API_KEY",
    openai: false,
    draft: {
      model: "",
      baseUrl: "",
      apiKey: "",
      stream: true,
      temperature: null,
      topP: null,
      maxTokens: "128000",
      thinking: null,
      reasoning: "",
      parallelTools: null,
      parameters: {},
    },
  },
  {
    id: "gemini",
    label: "Gemini",
    apiKeyEnv: "GEMINI_API_KEY",
    openai: false,
    draft: {
      model: "",
      baseUrl: "",
      apiKey: "",
      stream: null,
      temperature: null,
      topP: null,
      maxTokens: "",
      thinking: null,
      reasoning: "",
      parallelTools: null,
      parameters: {},
    },
  },
];

const builtinWallpapers = [
  { id: "aurora", name: "极光", src: aurora },
  { id: "ice", name: "冰纹", src: ice },
] as const;

const DEFAULT_WALLPAPER_ID = builtinWallpapers[0].id;

function copyDraft(draft: CardDraft): CardDraft {
  return { ...draft };
}

function defaultDrafts(): Record<CardId, CardDraft> {
  return {
    openai_chat: copyDraft(CARD_LIST[0].draft),
    openai_response: copyDraft(CARD_LIST[1].draft),
    anthropic: copyDraft(CARD_LIST[2].draft),
    gemini: copyDraft(CARD_LIST[3].draft),
  };
}

function defaults(): SettingsState {
  return {
    card: "openai_chat",
    drafts: defaultDrafts(),
    cores: 1,
    memoryBackend: "memory",
    localPath: "",
    systemPrompt: "",
    wallpaperId: DEFAULT_WALLPAPER_ID,
    uploads: [],
  };
}

function cardSpec(id: CardId): CardSpec {
  return CARD_LIST.find((item) => item.id === id) ?? CARD_LIST[0];
}

function isCardId(value: unknown): value is CardId {
  return typeof value === "string" && value.trim().length > 0;
}

function optionalBool(value: unknown, fallback: boolean | null): boolean | null {
  if (value === null) return null;
  if (typeof value === "boolean") return value;
  return fallback;
}

function optionalNumber(value: unknown, fallback: number | null): number | null {
  if (value === null) return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return fallback;
}

function tokenText(value: unknown, fallback: string): string {
  if (value === "") return "";
  if (typeof value !== "string" || !/^\d+$/.test(value)) return fallback;
  return value;
}

function reasoningOf(value: unknown, fallback: Reasoning): Reasoning {
  if (value === "" || value === "low" || value === "medium" || value === "high") return value;
  return fallback;
}

const legacyDraft: Record<CardId, { model: string; baseUrl: string }> = {
  openai_chat: { model: "deepseek-flash", baseUrl: "https://api.deepseek.com" },
  openai_response: { model: "gpt-6-astra", baseUrl: "https://eapi.site/v1" },
  anthropic: { model: "claude-opus-5", baseUrl: "https://eapi.site" },
  gemini: { model: "your-gemini-model", baseUrl: "" },
};

function withoutLegacy(id: CardId, model: string, baseUrl: string) {
  const legacy = legacyDraft[id];
  if (!legacy) return { model, baseUrl };
  return {
    model: model === legacy.model ? "" : model,
    baseUrl: baseUrl === legacy.baseUrl ? "" : baseUrl,
  };
}

function mergeDraft(id: CardId, value: unknown): CardDraft {
  const base = copyDraft(cardSpec(id).draft);
  if (!value || typeof value !== "object") return base;
  const row = value as Partial<CardDraft>;
  const model = typeof row.model === "string" ? row.model : base.model;
  const baseUrl = typeof row.baseUrl === "string" ? row.baseUrl : base.baseUrl;
  const cleared = withoutLegacy(id, model, baseUrl);
  return {
    model: cleared.model,
    baseUrl: cleared.baseUrl,
    apiKey: typeof row.apiKey === "string" ? row.apiKey : base.apiKey,
    stream: optionalBool(row.stream, base.stream),
    temperature: optionalNumber(row.temperature, base.temperature),
    topP: optionalNumber(row.topP, base.topP),
    maxTokens: tokenText(row.maxTokens, base.maxTokens),
    thinking: optionalBool(row.thinking, base.thinking),
    reasoning: reasoningOf(row.reasoning, base.reasoning),
    parallelTools: optionalBool(row.parallelTools, base.parallelTools),
    parameters: textParameters(row.parameters, base.parameters),
  };
}

function textParameters(value: unknown, fallback: Record<string, string>): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return { ...fallback };
  return Object.fromEntries(
    Object.entries(value).flatMap(([key, item]) =>
      typeof item === "string" ? [[key, item]] : [],
    ),
  );
}

function parse(value: unknown): SettingsState {
  const base = defaults();
  if (!value || typeof value !== "object") return base;
  const row = value as Partial<SettingsState>;
  const storedDrafts = row.drafts;
  const cores = typeof row.cores === "number" ? Math.floor(row.cores) : base.cores;
  const uploads = Array.isArray(row.uploads)
    ? row.uploads.flatMap((item) => {
        if (!item || typeof item !== "object") return [];
        const upload = item as Partial<UploadMeta>;
        if (typeof upload.id !== "string" || typeof upload.name !== "string") return [];
        return [{ id: upload.id, name: upload.name }];
      })
    : [];
  const card = isCardId(row.card) ? row.card : base.card;
  const drafts = {
      openai_chat: mergeDraft("openai_chat", storedDrafts?.openai_chat),
      openai_response: mergeDraft("openai_response", storedDrafts?.openai_response),
      anthropic: mergeDraft("anthropic", storedDrafts?.anthropic),
      gemini: mergeDraft("gemini", storedDrafts?.gemini),
    } as Record<CardId, CardDraft>;
  if (!drafts[card]) drafts[card] = copyDraft(CARD_LIST[0].draft);
  return {
    card,
    drafts,
    cores: cores >= 1 ? cores : 1,
    memoryBackend: row.memoryBackend === "local" ? "local" : "memory",
    localPath: typeof row.localPath === "string" ? row.localPath : "",
    systemPrompt: typeof row.systemPrompt === "string" ? row.systemPrompt : "",
    wallpaperId: typeof row.wallpaperId === "string" && row.wallpaperId ? row.wallpaperId : DEFAULT_WALLPAPER_ID,
    uploads,
  };
}

function load(): SettingsState {
  if (typeof localStorage === "undefined") return defaults();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaults();
    return parse(JSON.parse(raw));
  } catch {
    return defaults();
  }
}

let state = load();
const listeners = new Set<() => void>();

function commit(next: SettingsState) {
  state = next;
  try {
    const persisted = {
      ...next,
      drafts: Object.fromEntries(
        Object.entries(next.drafts).map(([id, draft]) => [id, { ...draft, apiKey: "" }]),
      ),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted));
  } catch {
    // 配额满了时，这次选择仍留在内存里。
  }
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getState() {
  return state;
}

const imageCache = new Map<string, string>();
let imageRevision = 0;
const imageListeners = new Set<() => void>();
let imagesStarted = false;
let database: Promise<IDBDatabase> | null = null;

function bumpImages() {
  imageRevision += 1;
  for (const listener of imageListeners) listener();
}

function subscribeImages(listener: () => void) {
  imageListeners.add(listener);
  return () => imageListeners.delete(listener);
}

function getImageRevision() {
  return imageRevision;
}

function openDb(): Promise<IDBDatabase> {
  if (!database) {
    database = new Promise((resolve, reject) => {
      const request = indexedDB.open("linope", 1);
      request.onupgradeneeded = () => {
        request.result.createObjectStore("wallpapers");
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }
  return database;
}

function isImageRow(value: unknown): value is { id: string; dataUrl: string } {
  if (!value || typeof value !== "object") return false;
  const row = value as { id?: unknown; dataUrl?: unknown };
  return typeof row.id === "string" && typeof row.dataUrl === "string";
}

async function loadImages() {
  const base = await openDb();
  const rows = await new Promise<Array<{ id: string; dataUrl: string }>>((resolve, reject) => {
    const request = base.transaction("wallpapers", "readonly").objectStore("wallpapers").getAll();
    request.onsuccess = () => {
      const result = Array.isArray(request.result) ? request.result : [];
      resolve(result.filter(isImageRow));
    };
    request.onerror = () => reject(request.error);
  });
  for (const row of rows) imageCache.set(row.id, row.dataUrl);
  bumpImages();
}

function ensureImages() {
  if (imagesStarted || typeof indexedDB === "undefined") return;
  imagesStarted = true;
  void loadImages().catch(() => {
    // 读不到本机图库时，自带壁纸仍然可用。
  });
}

function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") resolve(reader.result);
      else reject(new Error("unread"));
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function putImage(id: string, dataUrl: string) {
  const base = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = base.transaction("wallpapers", "readwrite");
    tx.objectStore("wallpapers").put({ id, dataUrl }, id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

function contextLimit(model: string): number {
  const name = model.toLowerCase();
  for (const [key, limit] of contextKeys) {
    if (name.includes(key)) return limit;
  }
  return FALLBACK_CONTEXT;
}

function wallpaperById(id: string): string | null {
  const builtin = builtinWallpapers.find((item) => item.id === id);
  if (builtin) return builtin.src;
  return imageCache.get(id) ?? null;
}

function useSettings() {
  return useSyncExternalStore(subscribe, getState, getState);
}

function useImageRevision() {
  return useSyncExternalStore(subscribeImages, getImageRevision, getImageRevision);
}

function useWallpaperSrc() {
  ensureImages();
  const current = useSettings();
  useImageRevision();
  return wallpaperById(current.wallpaperId) ?? builtinWallpapers[0].src;
}

function setCard(card: CardId) {
  if (card === state.card) return;
  commit({
    ...state,
    card,
    drafts: {
      ...state.drafts,
      [card]: state.drafts[card] ?? copyDraft(CARD_LIST[0].draft),
    },
  });
}

function updateDraft(patch: Partial<CardDraft>) {
  const card = state.card;
  const current = state.drafts[card] ?? copyDraft(CARD_LIST[0].draft);
  commit({
    ...state,
    drafts: {
      ...state.drafts,
      [card]: { ...current, ...patch },
    },
  });
}

function setDynamicCard(card: CardId, draft: Partial<CardDraft>) {
  const current = state.drafts[card] ?? copyDraft(CARD_LIST[0].draft);
  commit({
    ...state,
    card,
    drafts: {
      ...state.drafts,
      [card]: { ...current, ...draft, apiKey: "" },
    },
  });
}

function setCores(count: number) {
  const next = Math.max(1, Math.floor(count));
  if (next === state.cores) return;
  commit({ ...state, cores: next });
}

function setMemoryBackend(memoryBackend: MemoryBackend) {
  if (memoryBackend === state.memoryBackend) return;
  commit({ ...state, memoryBackend });
}

function setLocalPath(localPath: string) {
  if (localPath === state.localPath) return;
  commit({ ...state, localPath });
}

function setSystemPrompt(systemPrompt: string) {
  if (systemPrompt === state.systemPrompt) return;
  commit({ ...state, systemPrompt });
}

function setWallpaper(wallpaperId: string) {
  if (wallpaperId === state.wallpaperId) return;
  commit({ ...state, wallpaperId });
}

async function addWallpaper(file: File) {
  if (!file.type.startsWith("image/")) return;
  const dataUrl = await readFile(file);
  const id = crypto.randomUUID();
  imageCache.set(id, dataUrl);
  bumpImages();
  try {
    await putImage(id, dataUrl);
  } catch {
    // 写不进本机图库时，这张图在本次打开里仍可选。
  }
  const now = getState();
  commit({
    ...now,
    uploads: [...now.uploads, { id, name: file.name || "壁纸" }],
    wallpaperId: id,
  });
}

export {
  CARD_LIST,
  addWallpaper,
  builtinWallpapers,
  cardSpec,
  contextLimit,
  setCard,
  setCores,
  setDynamicCard,
  setMemoryBackend,
  setLocalPath,
  setSystemPrompt,
  setWallpaper,
  updateDraft,
  useImageRevision,
  useSettings,
  useWallpaperSrc,
  wallpaperById,
};
export type { CardDraft, CardId, Reasoning, SettingsState };
