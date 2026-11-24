import { useEffect, useState } from "react";
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

export const appId = "file:文件";

type Entry = { kind: string; name: string };
type Hit = { file: string; line: number; text: string };

const imageSuffixes = [".png", ".jpg", ".jpeg", ".webp", ".gif"];

function joinPath(dir: string, name: string) {
  if (!dir || dir === ".") return name;
  const sep = dir.includes("\\") ? "\\" : "/";
  return dir.endsWith(sep) ? `${dir}${name}` : `${dir}${sep}${name}`;
}

function parentPath(dir: string) {
  const trimmed = dir.replace(/[\\/]+$/, "");
  const index = Math.max(trimmed.lastIndexOf("\\"), trimmed.lastIndexOf("/"));
  if (index < 0) return dir;
  const parent = trimmed.slice(0, index);
  if (/^[A-Za-z]:$/.test(parent)) return `${parent}\\`;
  return parent || dir;
}

function stripNumbers(content: string) {
  return content
    .split("\n")
    .map((line) => line.replace(/^\s*\d+\|/, ""))
    .join("\n");
}

function isImage(path: string) {
  const lower = path.toLowerCase();
  return imageSuffixes.some((suffix) => lower.endsWith(suffix));
}

export default function FileDesktop({ call, cwd = "" }: { call?: CapabilityCaller; cwd?: string }) {
  const root = cwd || ".";
  const [path, setPath] = useState(root);
  const [draftPath, setDraftPath] = useState(root);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [filePath, setFilePath] = useState("");
  const [text, setText] = useState("");
  const [image, setImage] = useState("");
  const [mediaType, setMediaType] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [created, setCreated] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function invoke(input: Parameters<CapabilityCaller>[0]) {
    if (!call) throw new Error("当前没有连上内核，不能直接操作。");
    setError("");
    setNotice("");
    return runCall(call, { cwd: root, hold: true, ...input });
  }

  async function openDir(next: string) {
    const payload = await invoke({
      body: { path: next },
      capability: "tools.list_dir",
      kind: "tool",
    });
    const listed = String(payload.path || next);
    const rows = Array.isArray(payload.entries) ? (payload.entries as Entry[]) : [];
    setPath(listed);
    setDraftPath(listed);
    setEntries(rows.filter((item) => item && typeof item.name === "string"));
    setHits([]);
  }

  async function openFile(next: string) {
    if (isImage(next)) {
      const payload = await invoke({
        body: { data: true, file_path: next },
        capability: "tools.read_image",
        kind: "tool",
      });
      setFilePath(String(payload.path || next));
      setImage(String(payload.data || ""));
      setMediaType(String(payload.mediaType || "image/png"));
      setText("");
      return;
    }
    const payload = await invoke({
      body: { file_path: next },
      capability: "tools.read",
      kind: "tool",
    });
    setFilePath(String(payload.path || next));
    setText(stripNumbers(String(payload.content || "")));
    setImage("");
  }

  useEffect(() => {
    if (!call) {
      setError("当前没有连上内核，不能直接操作。");
      return;
    }
    let cancel = false;
    invoke({ body: { path: root }, capability: "tools.list_dir", kind: "tool" })
      .then((payload) => {
        if (cancel) return;
        const listed = String(payload.path || root);
        const rows = Array.isArray(payload.entries) ? (payload.entries as Entry[]) : [];
        setPath(listed);
        setDraftPath(listed);
        setEntries(rows.filter((item) => item && typeof item.name === "string"));
      })
      .catch((caught: unknown) => {
        if (!cancel) setError(caught instanceof Error ? caught.message : String(caught));
      });
    return () => {
      cancel = true;
    };
  }, [call, root]);

  return (
    <AppFrame>
      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={() => openDir(parentPath(path)).catch(() => undefined)} style={buttonStyle} type="button">
          上一级
        </button>
        <input
          aria-label="当前路径"
          onChange={(event) => setDraftPath(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") openDir(draftPath).catch(() => undefined);
          }}
          style={fieldStyle}
          value={draftPath}
        />
        <button onClick={() => openDir(draftPath).catch(() => undefined)} style={buttonStyle} type="button">
          打开
        </button>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          aria-label="在文件夹中搜索"
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || !query.trim()) return;
            invoke({ body: { path, pattern: query.trim() }, capability: "tools.grep", kind: "tool" })
              .then((payload) => {
                const matches = payload.matches;
                const rows: Hit[] = [];
                if (matches && typeof matches === "object") {
                  for (const [file, lines] of Object.entries(matches as Record<string, unknown>)) {
                    if (!Array.isArray(lines)) continue;
                    for (const line of lines) {
                      if (!line || typeof line !== "object") continue;
                      const row = line as { line?: unknown; text?: unknown };
                      rows.push({ file, line: Number(row.line) || 0, text: String(row.text || "") });
                    }
                  }
                }
                setHits(rows);
              })
              .catch(() => undefined);
          }}
          placeholder="在这个文件夹里搜索"
          style={fieldStyle}
          value={query}
        />
        <input
          aria-label="新文件名"
          onChange={(event) => setCreated(event.target.value)}
          placeholder="新文件名"
          style={{ ...fieldStyle, maxWidth: 160 }}
          value={created}
        />
        <button
          onClick={() => {
            const name = created.trim();
            if (!name) return;
            const next = joinPath(path, name);
            invoke({ body: { content: "", file_path: next }, capability: "tools.write", kind: "tool" })
              .then(() => openDir(path))
              .then(() => openFile(next))
              .catch(() => undefined);
          }}
          style={buttonStyle}
          type="button"
        >
          新建
        </button>
      </div>
      <ErrorLine>{error}</ErrorLine>
      {notice ? <p style={{ color: quiet, fontSize: 13, lineHeight: "18px", margin: 0 }}>{notice}</p> : null}
      <div style={{ display: "flex", flex: 1, gap: 10, minHeight: 0 }}>
        <div style={{ ...cardStyle, flex: "0 0 220px", minHeight: 0, overflow: "auto", padding: 8 }}>
          {entries.length === 0 ? <EmptyPane>这个文件夹是空的。</EmptyPane> : null}
          {entries.map((entry) => (
            <button
              key={`${entry.kind}:${entry.name}`}
              onClick={() => {
                const next = joinPath(path, entry.name);
                if (entry.kind === "dir") openDir(next).catch(() => undefined);
                else openFile(next).catch(() => undefined);
              }}
              style={{
                background: "transparent",
                border: 0,
                color: ink,
                cursor: "pointer",
                display: "block",
                fontSize: 14,
                lineHeight: "20px",
                padding: "6px 8px",
                textAlign: "left",
                width: "100%",
              }}
              type="button"
            >
              {entry.kind === "dir" ? `${entry.name}/` : entry.name}
            </button>
          ))}
        </div>
        <div style={{ ...cardStyle, display: "flex", flex: 1, flexDirection: "column", minHeight: 0, minWidth: 0, padding: 10 }}>
          {hits.length > 0 ? (
            <div style={{ maxHeight: 140, overflow: "auto" }}>
              {hits.map((hit) => (
                <button
                  key={`${hit.file}:${hit.line}:${hit.text}`}
                  onClick={() => openFile(joinPath(path, hit.file)).catch(() => undefined)}
                  style={{
                    background: "transparent",
                    border: 0,
                    color: ink,
                    cursor: "pointer",
                    display: "block",
                    fontSize: 13,
                    lineHeight: "18px",
                    padding: "4px 0",
                    textAlign: "left",
                    width: "100%",
                  }}
                  type="button"
                >
                  {hit.file}:{hit.line} {hit.text}
                </button>
              ))}
            </div>
          ) : null}
          {image ? (
            <img
              alt={filePath}
              src={`data:${mediaType};base64,${image}`}
              style={{ maxHeight: "100%", maxWidth: "100%", objectFit: "contain" }}
            />
          ) : filePath ? (
            <>
              <div style={{ alignItems: "center", display: "flex", gap: 8 }}>
                <span style={{ flex: 1, fontSize: 13, lineHeight: "18px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {filePath}
                </span>
                <button
                  onClick={() => {
                    invoke({ body: { content: text, file_path: filePath }, capability: "tools.write", kind: "tool" })
                      .then(() => setNotice("已保存"))
                      .catch(() => undefined);
                  }}
                  style={buttonStyle}
                  type="button"
                >
                  保存
                </button>
              </div>
              <textarea
                onChange={(event) => setText(event.target.value)}
                spellCheck={false}
                style={{ ...fieldStyle, flex: 1, fontFamily: "ui-monospace, Consolas, monospace", minHeight: 0, resize: "none" }}
                value={text}
              />
            </>
          ) : (
            <EmptyPane>选一个文件就能查看和修改。图片会显示画面。</EmptyPane>
          )}
        </div>
      </div>
    </AppFrame>
  );
}
