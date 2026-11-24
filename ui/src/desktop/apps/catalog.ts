import { introductions } from "virtual:capability-desktops";

type AppId = "file" | "code" | "terminal" | "other" | "sandbox" | "context" | "loop" | "mcp";

type AppFeature = {
  name: string;
  detail: string;
};

type AppEntry = {
  id: AppId;
  name: string;
  summary: string;
  featured: boolean;
  features: AppFeature[];
};

type Shelf = {
  id: AppId;
  name: string;
  summary?: string;
  featured?: boolean;
};

const SHELVES: Shelf[] = [
  { id: "file", name: "文件", featured: true },
  { id: "code", name: "代码", featured: true },
  { id: "terminal", name: "终端" },
  { id: "other", name: "其它" },
  { id: "sandbox", name: "沙箱", featured: true },
  { id: "context", name: "上下文", featured: true },
  { id: "loop", name: "循环", summary: "按步骤完成一项任务，直到给出结果。", featured: true },
  { id: "mcp", name: "MCP" },
];

function splitAppId(appId: string) {
  const index = appId.indexOf(":");
  if (index <= 0 || index === appId.length - 1) {
    throw new Error(`appId 应为「分类:名称」：${appId}`);
  }
  return { categoryId: appId.slice(0, index), name: appId.slice(index + 1) };
}

const featuresByCategory = new Map<string, Array<AppFeature & { summary: string }>>();
for (const [appId, introduction] of Object.entries(introductions)) {
  const { categoryId, name } = splitAppId(appId);
  const rows = featuresByCategory.get(categoryId) ?? [];
  rows.push({ name, detail: introduction.detail, summary: introduction.summary });
  featuresByCategory.set(categoryId, rows);
}

for (const categoryId of featuresByCategory.keys()) {
  if (!SHELVES.some((shelf) => shelf.id === categoryId)) {
    throw new Error(`应用分类不在货架上：${categoryId}`);
  }
}

const APPS: AppEntry[] = SHELVES.flatMap((shelf) => {
  const rows = featuresByCategory.get(shelf.id) ?? [];
  if (rows.length === 0) return [];
  const summary = shelf.summary ?? (rows.length === 1 ? rows[0].summary : "");
  return [
    {
      id: shelf.id,
      name: shelf.name,
      summary,
      featured: Boolean(shelf.featured),
      features: rows.map(({ name, detail }) => ({ name, detail })),
    },
  ];
});

export type { AppEntry, AppFeature, AppId };
export { APPS };
