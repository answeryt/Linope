import { useEffect, useState, type CSSProperties, type RefObject } from "react";
import { dialogSurface } from "@/desktop/dialog/glass";
import { lensShadow } from "@/desktop/dialog/ChatPanel";

const TEXT_LIMIT = 200 * 1024;
const TEXT_EXTENSIONS = new Set([
  "txt", "md", "json", "csv", "log", "ts", "tsx", "js", "jsx", "mjs", "cjs",
  "py", "css", "html", "xml", "yml", "yaml", "toml", "ini", "sh", "c", "h",
  "rs", "go", "java", "kt", "swift", "rb", "php", "sql", "vue", "svelte",
  "scss", "less",
]);

type AttachmentKind = "image" | "text" | "file" | "folder";

type Attachment = {
  id: string;
  path: string;
  name: string;
  size: number;
  kind: AttachmentKind;
  file: File;
  previewUrl: string;
};

const attachmentSize = 44;
const attachmentGap = 10;

function attachmentAnchor(width: number, height: number, bottom: number): CSSProperties {
  return {
    position: "absolute",
    width: attachmentSize,
    height: attachmentSize,
    left: `calc(50% - min(${width}px, calc(100% - 48px)) / 2 - ${attachmentSize + attachmentGap}px)`,
    bottom: bottom + Math.max(0, (height - attachmentSize) / 2),
    borderRadius: 999,
  };
}

function extensionOf(name: string) {
  const dot = name.lastIndexOf(".");
  if (dot <= 0 || dot === name.length - 1) return "";
  return name.slice(dot + 1).toLowerCase();
}

function extensionLabel(name: string) {
  const ext = extensionOf(name);
  return ext ? ext.slice(0, 4).toUpperCase() : "文件";
}

function kindOf(file: File, directory: boolean): AttachmentKind {
  if (directory) return "folder";
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("text/") || TEXT_EXTENSIONS.has(extensionOf(file.name))) return "text";
  return "file";
}

function isDirectory(item: DataTransferItem | undefined) {
  const entry = item?.webkitGetAsEntry?.();
  return Boolean(entry?.isDirectory);
}

function attachmentsFromDrop(files: FileList, items: DataTransferItemList | undefined) {
  const pathFor = window.linopeKernel?.files?.pathFor;
  if (!pathFor) return [];
  const next: Attachment[] = [];
  Array.from(files).forEach((file, index) => {
    let found = "";
    try {
      found = pathFor(file).trim();
    } catch {
      found = "";
    }
    if (!found) return;
    const kind = kindOf(file, isDirectory(items?.[index]));
    next.push({
      id: found,
      path: found,
      name: file.name || found.split(/[\\/]/).pop() || found,
      size: file.size,
      kind,
      file,
      previewUrl: kind === "image" ? URL.createObjectURL(file) : "",
    });
  });
  return next;
}

function mergeAttachments(current: Attachment[], incoming: Attachment[]) {
  const seen = new Set(current.map((item) => item.path));
  const added = incoming.filter((item) => {
    if (seen.has(item.path)) {
      if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      return false;
    }
    seen.add(item.path);
    return true;
  });
  return added.length ? [...current, ...added] : current;
}

function releaseAttachments(items: Attachment[]) {
  for (const item of items) {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  }
}

function messageWithAttachments(text: string, items: Attachment[]) {
  const body = text.trim();
  const paths = items.map((item) => item.path);
  if (!paths.length) return body;
  if (!body) return paths.join("\n");
  return `${body}\n${paths.join("\n")}`;
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(size < 10 * 1024 ? 1 : 0)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function FileMark({ label }: { label: string }) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: "grid",
        width: 28,
        height: 28,
        placeItems: "center",
        borderRadius: 8,
        background: "rgba(28,28,30,0.88)",
        color: "#fff",
        fontSize: 9,
        fontWeight: 700,
        lineHeight: "12px",
      }}
    >
      {label}
    </span>
  );
}

function AttachmentCircle({
  circleRef,
  height,
  items,
  onToggle,
  open,
  width,
  bottom,
}: {
  circleRef: RefObject<HTMLButtonElement | null>;
  height: number;
  items: Attachment[];
  onToggle: () => void;
  open: boolean;
  width: number;
  bottom: number;
}) {
  const latest = items[items.length - 1];
  if (!latest) return null;
  return (
    <button
      aria-expanded={open}
      aria-label={open ? "收起附件" : "查看附件"}
      className="pointer-events-auto cursor-pointer border-0 p-0"
      onClick={onToggle}
      ref={circleRef}
      style={{
        ...attachmentAnchor(width, height, bottom),
        zIndex: 32,
        background: "transparent",
        boxShadow: lensShadow,
        color: "#1c1c1e",
      }}
      type="button"
    >
      {latest.kind === "image" && latest.previewUrl ? (
        <span style={{ display: "block", width: "100%", height: "100%", overflow: "hidden", borderRadius: 999 }}>
          <img
            alt=""
            draggable={false}
            src={latest.previewUrl}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </span>
      ) : (
        <span className="grid h-full w-full place-items-center">
          <FileMark label={latest.kind === "folder" ? "夹" : extensionLabel(latest.name)} />
        </span>
      )}
      {items.length > 1 ? (
        <span
          style={{
            position: "absolute",
            top: -2,
            right: -2,
            minWidth: 18,
            height: 18,
            padding: "0 4px",
            borderRadius: 999,
            background: "rgba(28,28,30,0.88)",
            color: "#fff",
            fontSize: 11,
            lineHeight: "18px",
          }}
        >
          {items.length}
        </span>
      ) : null}
    </button>
  );
}

function AttachmentPreview({
  bottom,
  items,
  onOpen,
  onRemove,
  previewRef,
}: {
  bottom: number;
  items: Attachment[];
  onOpen: (path: string) => Promise<string>;
  onRemove: (id: string) => void;
  previewRef: RefObject<HTMLDivElement | null>;
}) {
  const [selectedId, setSelectedId] = useState(items[items.length - 1]?.id ?? "");
  const selected = items.find((item) => item.id === selectedId) ?? items[items.length - 1];
  const [body, setBody] = useState<{ id: string; text: string; truncated: boolean; error: boolean } | null>(null);
  const [openError, setOpenError] = useState("");

  useEffect(() => {
    if (!selected || selected.kind !== "text") return;
    let cancel = false;
    setBody(null);
    selected.file
      .slice(0, TEXT_LIMIT)
      .text()
      .then((text) => {
        if (cancel) return;
        setBody({
          id: selected.id,
          text,
          truncated: selected.file.size > TEXT_LIMIT,
          error: false,
        });
      })
      .catch(() => {
        if (!cancel) setBody({ id: selected.id, text: "", truncated: false, error: true });
      });
    return () => {
      cancel = true;
    };
  }, [selected]);

  if (!selected) return null;
  const textReady = body?.id === selected.id ? body : null;

  return (
    <div
      className="pointer-events-auto absolute"
      ref={previewRef}
      style={{
        ...dialogSurface,
        left: "50%",
        bottom,
        transform: "translateX(-50%)",
        zIndex: 41,
        width: "min(440px, calc(100% - 32px))",
        borderRadius: 22,
        padding: 12,
        color: "#1c1c1e",
      }}
    >
      <div className="flex gap-2 overflow-x-auto pb-1" style={{ scrollbarWidth: "thin" }}>
        {items.map((item) => {
          const chosen = item.id === selected.id;
          return (
            <div key={item.id} style={{ position: "relative", flex: "0 0 auto" }}>
              <button
                aria-label={item.name}
                aria-pressed={chosen}
                className="cursor-pointer overflow-hidden border-0 p-0"
                onClick={() => {
                  setSelectedId(item.id);
                  setOpenError("");
                }}
                style={{
                  width: 76,
                  height: 76,
                  borderRadius: 16,
                  background: "rgba(255,255,255,0.5)",
                  boxShadow: chosen ? "inset 0 0 0 2px rgba(28,28,30,0.85)" : undefined,
                  color: "#1c1c1e",
                }}
                type="button"
              >
                {item.kind === "image" && item.previewUrl ? (
                  <img alt="" draggable={false} src={item.previewUrl} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                ) : (
                  <span className="flex h-full w-full flex-col items-center justify-center gap-1 px-1">
                    <FileMark label={item.kind === "folder" ? "夹" : extensionLabel(item.name)} />
                    <span
                      style={{
                        maxWidth: "100%",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        fontSize: 11,
                        lineHeight: "14px",
                      }}
                    >
                      {item.name}
                    </span>
                  </span>
                )}
              </button>
              <button
                aria-label={`移除 ${item.name}`}
                className="absolute cursor-pointer border-0 p-0"
                onClick={() => onRemove(item.id)}
                style={{
                  top: 4,
                  right: 4,
                  width: 18,
                  height: 18,
                  borderRadius: 999,
                  background: "rgba(28,28,30,0.72)",
                  color: "#fff",
                  fontSize: 12,
                  lineHeight: "18px",
                }}
                type="button"
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 12 }}>
        {selected.kind === "image" && selected.previewUrl ? (
          <img
            alt={selected.name}
            draggable={false}
            src={selected.previewUrl}
            style={{ display: "block", width: "100%", maxHeight: 360, objectFit: "contain", borderRadius: 14 }}
          />
        ) : null}
        {selected.kind === "text" ? (
          <pre
            style={{
              margin: 0,
              maxHeight: 240,
              overflow: "auto",
              whiteSpace: "pre-wrap",
              overflowWrap: "anywhere",
              fontSize: 13,
              lineHeight: "18px",
            }}
          >
            {textReady?.error
              ? "这份文件读不出来。"
              : textReady
                ? `${textReady.text}${textReady.truncated ? "\n…（只显示前 200 KB）" : ""}`
                : "正在读取…"}
          </pre>
        ) : null}
        {selected.kind === "file" || selected.kind === "folder" ? (
          <div className="flex flex-col gap-1">
            <span style={{ fontSize: 15, fontWeight: 650, lineHeight: "20px" }}>{selected.name}</span>
            <span style={{ fontSize: 13, lineHeight: "18px", color: "rgba(60,60,67,0.72)" }}>
              {selected.kind === "folder" ? "文件夹" : formatSize(selected.size)}
            </span>
            <span style={{ fontSize: 13, lineHeight: "18px", overflowWrap: "anywhere", color: "rgba(60,60,67,0.72)" }}>
              {selected.path}
            </span>
          </div>
        ) : null}
        {selected.kind !== "image" ? (
          <button
            className="cursor-pointer border-0"
            onClick={() => {
              setOpenError("");
              void onOpen(selected.path).then((message) => {
                if (message) setOpenError(message);
              });
            }}
            style={{
              marginTop: 10,
              borderRadius: 999,
              background: "rgba(255,255,255,0.82)",
              padding: "6px 12px",
              fontSize: 13,
              lineHeight: "18px",
            }}
            type="button"
          >
            用系统应用打开
          </button>
        ) : null}
        {openError ? (
          <p style={{ margin: "8px 0 0", color: "#8b1e2d", fontSize: 13, lineHeight: "18px" }}>{openError}</p>
        ) : null}
      </div>
    </div>
  );
}

export type { Attachment };
export {
  attachmentAnchor,
  attachmentsFromDrop,
  mergeAttachments,
  messageWithAttachments,
  releaseAttachments,
  AttachmentCircle,
  AttachmentPreview,
};
