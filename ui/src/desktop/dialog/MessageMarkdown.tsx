import { useMemo, type CSSProperties, type ReactNode } from "react";
import { Marked, type Token, type Tokens } from "marked";
import markedCjkFriendly from "marked-cjk-friendly";

const markdown = new Marked({ breaks: true, gfm: true });
markdown.use(markedCjkFriendly());

const rootStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 8,
  minWidth: 0,
  overflowWrap: "anywhere",
};

const paragraphStyle: CSSProperties = {
  margin: 0,
};

const listStyle: CSSProperties = {
  margin: 0,
  paddingLeft: 22,
};

const codeStyle: CSSProperties = {
  background: "rgba(28,28,30,0.08)",
  borderRadius: 4,
  fontFamily: "var(--font-mono)",
  fontSize: "0.9em",
  padding: "1px 4px",
};

const codeBlockStyle: CSSProperties = {
  background: "rgba(28,28,30,0.08)",
  borderRadius: 8,
  fontFamily: "var(--font-mono)",
  fontSize: 13,
  lineHeight: "18px",
  margin: 0,
  maxWidth: "100%",
  overflowX: "auto",
  padding: "8px 10px",
  whiteSpace: "pre",
};

const blockquoteStyle: CSSProperties = {
  borderLeft: "3px solid rgba(28,28,30,0.22)",
  margin: 0,
  paddingLeft: 10,
};

const linkStyle: CSSProperties = {
  color: "inherit",
  textDecoration: "underline",
};

const tableStyle: CSSProperties = {
  borderCollapse: "collapse",
  margin: 0,
  minWidth: "100%",
};

const tableCellStyle: CSSProperties = {
  border: "1px solid rgba(28,28,30,0.18)",
  padding: "4px 7px",
  textAlign: "left",
};

function safeHref(href: string): string | undefined {
  const target = href.trim();
  return /^(https?:|mailto:)/i.test(target) ? target : undefined;
}

function inline(
  tokens: readonly Token[] | undefined,
  key: string,
  inLink = false,
): ReactNode[] {
  return (tokens ?? []).map((token, index) =>
    inlineToken(token, `${key}-${index}`, inLink),
  );
}

function inlineToken(token: Token, key: string, inLink: boolean): ReactNode {
  switch (token.type) {
    case "text":
      return token.tokens ? (
        <span key={key}>{inline(token.tokens, key, inLink)}</span>
      ) : (
        <span key={key}>{token.text}</span>
      );
    case "escape":
      return <span key={key}>{token.text}</span>;
    case "strong":
      return <strong key={key}>{inline(token.tokens, key, inLink)}</strong>;
    case "em":
      return <em key={key}>{inline(token.tokens, key, inLink)}</em>;
    case "del":
      return <del key={key}>{inline(token.tokens, key, inLink)}</del>;
    case "codespan":
      return (
        <code key={key} style={codeStyle}>
          {token.text}
        </code>
      );
    case "br":
      return <br key={key} />;
    case "checkbox":
      return (
        <input
          aria-label={token.checked ? "已完成" : "未完成"}
          checked={token.checked}
          disabled
          key={key}
          readOnly
          type="checkbox"
        />
      );
    case "link": {
      const href = inLink ? undefined : safeHref(token.href);
      const children = inline(token.tokens, key, true);
      return href ? (
        <a
          href={href}
          key={key}
          rel="noreferrer"
          style={linkStyle}
          target="_blank"
          title={token.title ?? undefined}
        >
          {children}
        </a>
      ) : (
        <span key={key}>{children}</span>
      );
    }
    case "image": {
      const href = inLink ? undefined : safeHref(token.href);
      const label = token.text || token.href;
      return href ? (
        <a
          href={href}
          key={key}
          rel="noreferrer"
          style={linkStyle}
          target="_blank"
          title={token.title ?? undefined}
        >
          {label}
        </a>
      ) : (
        <span key={key}>{label}</span>
      );
    }
    case "html":
      return <span key={key}>{token.raw}</span>;
    default:
      return <span key={key}>{token.raw}</span>;
  }
}

function listItem(item: Tokens.ListItem, key: string): ReactNode {
  return (
    <li key={key}>
      {item.tokens.map((token, index) =>
        token.type === "text"
          ? inlineToken(token, `${key}-${index}`, false)
          : block(token, `${key}-${index}`),
      )}
    </li>
  );
}

function block(token: Token, key: string): ReactNode {
  switch (token.type) {
    case "space":
    case "def":
      return null;
    case "heading": {
      const tag = `h${Math.min(token.depth + 2, 6)}` as "h3" | "h4" | "h5" | "h6";
      return (
        <Heading key={key} level={tag}>
          {inline(token.tokens, key)}
        </Heading>
      );
    }
    case "paragraph":
    case "text":
      return (
        <p key={key} style={paragraphStyle}>
          {token.tokens ? inline(token.tokens, key) : token.text}
        </p>
      );
    case "code":
      return (
        <pre key={key} style={codeBlockStyle}>
          <code>{token.text}</code>
        </pre>
      );
    case "blockquote": {
      const quote = token as Tokens.Blockquote;
      return (
        <blockquote key={key} style={blockquoteStyle}>
          {quote.tokens.map((child, index) => block(child, `${key}-${index}`))}
        </blockquote>
      );
    }
    case "hr":
      return (
        <hr
          key={key}
          style={{ border: 0, borderTop: "1px solid rgba(28,28,30,0.2)", margin: 0 }}
        />
      );
    case "list": {
      const list = token as Tokens.List;
      const ListTag = list.ordered ? "ol" : "ul";
      return (
        <ListTag
          key={key}
          start={
            list.ordered && typeof list.start === "number" && list.start !== 1
              ? list.start
              : undefined
          }
          style={listStyle}
        >
          {list.items.map((item, index) => listItem(item, `${key}-${index}`))}
        </ListTag>
      );
    }
    case "table": {
      const table = token as Tokens.Table;
      return (
        <div key={key} style={{ maxWidth: "100%", overflowX: "auto" }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                {table.header.map((cell, index) => (
                  <th
                    key={`${key}-header-${index}`}
                    style={{ ...tableCellStyle, textAlign: cell.align ?? "left" }}
                  >
                    {inline(cell.tokens, `${key}-header-${index}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, rowIndex) => (
                <tr key={`${key}-row-${rowIndex}`}>
                  {row.map((cell, cellIndex) => (
                    <td
                      key={`${key}-cell-${rowIndex}-${cellIndex}`}
                      style={{ ...tableCellStyle, textAlign: cell.align ?? "left" }}
                    >
                      {inline(cell.tokens, `${key}-cell-${rowIndex}-${cellIndex}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    case "html":
      return <span key={key}>{token.raw}</span>;
    default:
      return <span key={key}>{token.raw}</span>;
  }
}

function Heading({
  children,
  level,
}: {
  children: ReactNode;
  level: "h3" | "h4" | "h5" | "h6";
}) {
  const style: CSSProperties = {
    fontSize: level === "h3" ? 16 : 15,
    fontWeight: 700,
    lineHeight: "20px",
    margin: 0,
  };
  return level === "h3" ? (
    <h3 style={style}>{children}</h3>
  ) : level === "h4" ? (
    <h4 style={style}>{children}</h4>
  ) : level === "h5" ? (
    <h5 style={style}>{children}</h5>
  ) : (
    <h6 style={style}>{children}</h6>
  );
}

function parseMarkdown(source: string): ReactNode[] {
  try {
    return markdown.lexer(source).map((token, index) => block(token, `block-${index}`));
  } catch {
    return [
      <span key="fallback" style={{ whiteSpace: "pre-wrap" }}>
        {source}
      </span>,
    ];
  }
}

function MessageMarkdown({ source }: { source: string }) {
  const content = useMemo(() => parseMarkdown(source), [source]);
  return <div style={rootStyle}>{content}</div>;
}

export { MessageMarkdown };
