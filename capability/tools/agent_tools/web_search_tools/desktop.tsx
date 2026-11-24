import { useState } from "react";
import {
  AppFrame,
  EmptyPane,
  ErrorLine,
  buttonStyle,
  cardStyle,
  fieldStyle,
  ink,
  quiet,
  runCall,
  type CapabilityCaller,
} from "@/desktop/apps/shell";

export const appId = "other:网页搜索";

const providers = [
  { id: "tools.ddgs", name: "DuckDuckGo" },
  { id: "tools.brave_free", name: "Brave" },
  { id: "tools.exa", name: "Exa" },
  { id: "tools.tavily", name: "Tavily" },
  { id: "tools.firecrawl", name: "Firecrawl" },
  { id: "tools.parallel", name: "Parallel" },
  { id: "tools.searxng", name: "SearXNG" },
];

type Result = { description: string; title: string; url: string };

export default function WebSearchDesktop({ call, cwd = "" }: { call?: CapabilityCaller; cwd?: string }) {
  const [provider, setProvider] = useState(providers[0].id);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);

  function search() {
    const text = query.trim();
    if (!text) return;
    if (!call) {
      setError("当前没有连上内核，不能直接操作。");
      return;
    }
    setError("");
    runCall(call, {
      body: { limit: 5, query: text },
      capability: provider,
      cwd,
      hold: true,
      kind: "tool",
    })
      .then((payload) => {
        const data = payload.data;
        const web =
          data && typeof data === "object" && Array.isArray((data as { web?: unknown }).web)
            ? ((data as { web: unknown[] }).web)
            : [];
        setResults(
          web.flatMap((item) => {
            if (!item || typeof item !== "object") return [];
            const row = item as { description?: unknown; title?: unknown; url?: unknown };
            return [{ description: String(row.description || ""), title: String(row.title || row.url || "结果"), url: String(row.url || "") }];
          }),
        );
        setSearched(true);
      })
      .catch((caught: unknown) => {
        setResults([]);
        setSearched(true);
        setError(caught instanceof Error ? caught.message : String(caught));
      });
  }

  return (
    <AppFrame>
      <div style={{ display: "flex", gap: 8 }}>
        <select
          aria-label="搜索服务"
          onChange={(event) => setProvider(event.target.value)}
          style={{ ...fieldStyle, maxWidth: 160, width: "auto" }}
          value={provider}
        >
          {providers.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
        <input
          aria-label="搜索"
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") search();
          }}
          placeholder="要查的问题"
          style={fieldStyle}
          value={query}
        />
        <button onClick={search} style={buttonStyle} type="button">
          搜索
        </button>
      </div>
      <ErrorLine>{error}</ErrorLine>
      <div style={{ ...cardStyle, flex: 1, minHeight: 0, overflow: "auto", padding: 12 }}>
        {!searched ? <EmptyPane>提出要查的问题，结果会列出标题、链接和摘要。</EmptyPane> : null}
        {searched && results.length === 0 && !error ? <EmptyPane>没有找到结果。</EmptyPane> : null}
        {results.map((item) => (
          <a
            href={item.url || undefined}
            key={`${item.url}:${item.title}`}
            rel="noreferrer"
            style={{ color: ink, display: "block", padding: "8px 0", textDecoration: "none" }}
            target="_blank"
          >
            <span style={{ display: "block", fontSize: 15, lineHeight: "22px" }}>{item.title}</span>
            {item.url ? (
              <span style={{ color: quiet, display: "block", fontSize: 12, lineHeight: "16px" }}>{item.url}</span>
            ) : null}
            {item.description ? (
              <span style={{ display: "block", fontSize: 13, lineHeight: "18px", marginTop: 2 }}>{item.description}</span>
            ) : null}
          </a>
        ))}
      </div>
    </AppFrame>
  );
}
