import { occupiedTokens } from "@/desktop/link/state";
import { useInstalledApps } from "@/desktop/apps/installed";
import { AppFrame, EmptyPane, cardStyle, quiet } from "@/desktop/apps/shell";
import { loadedPromptText } from "@/desktop/setting/loaded-loops";
import { contextLimit, useSettings } from "@/desktop/setting/settings";

export const appId = "context:上下文压缩工具";

const methods = [
  { detail: "去掉重复，缩短过长的记录，最近的话优先留下。", name: "语义" },
  { detail: "为较早的对话生成简要说明，留下任务目标和关键结论。", name: "摘要" },
  { detail: "保住开头和最近一段，中间按长度裁掉。", name: "滑动窗口" },
];

export default function ContextDesktop({ lines = [] }: { lines?: string[] }) {
  const settings = useSettings();
  const installed = useInstalledApps();
  const model = settings.drafts[settings.card].model.trim();
  const limit = contextLimit(model);
  const occupied = occupiedTokens(
    loadedPromptText(installed.map((app) => app.id), settings.promptOverrides),
    lines,
  );
  const recent = lines.slice(-12);

  return (
    <AppFrame>
      <div style={{ display: "flex", gap: 8 }}>
        {methods.map((item) => (
          <div key={item.name} style={{ ...cardStyle, flex: 1, padding: "12px 14px" }}>
            <div style={{ fontSize: 15, fontWeight: 650, lineHeight: "22px" }}>{item.name}</div>
            <div style={{ color: quiet, fontSize: 13, lineHeight: "18px" }}>{item.detail}</div>
          </div>
        ))}
      </div>
      <div style={{ ...cardStyle, flex: 1, minHeight: 0, overflow: "auto", padding: 14 }}>
        <div style={{ fontSize: 15, lineHeight: "22px" }}>
          {occupied > 0 ? occupied.toLocaleString("zh-CN") : "0"} / {limit.toLocaleString("zh-CN")}
        </div>
        <div style={{ color: quiet, fontSize: 13, lineHeight: "18px", marginTop: 4 }}>
          {model ? `当前模型 ${model}` : "还没选模型，上限用的是默认值。"}
        </div>
        {recent.length === 0 ? (
          <div style={{ marginTop: 16 }}>
            <EmptyPane>还没有对话。你发出一句话之后，这里会写出它占了多少，以及会留下什么。</EmptyPane>
          </div>
        ) : (
          recent.map((line, index) => (
            <p key={`${index}:${line.slice(0, 24)}`} style={{ fontSize: 14, lineHeight: "20px", margin: "12px 0 0" }}>
              {line}
            </p>
          ))
        )}
      </div>
    </AppFrame>
  );
}
