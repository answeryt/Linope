type AppId = "file" | "code" | "terminal" | "other" | "sandbox" | "context" | "loop" | "mcp";

type AppFeature = {
  name: string;
  detail: string;
};

type AppEntry = {
  id: AppId;
  name: string;
  summary: string;
  features: AppFeature[];
};

const APPS: AppEntry[] = [
  {
    id: "file",
    name: "文件",
    summary: "文件读写、编辑和目录访问。",
    features: [
      {
        name: "文件",
        detail: "read、write、edit、str_replace_editor、glob、grep、read_image，以及合并的 file_ops。",
      },
    ],
  },
  {
    id: "code",
    name: "代码",
    summary: "运行代码并处理代码相关任务。",
    features: [{ name: "运行代码", detail: "run_code 运行一个调用其他工具的 Python 程序，不是 shell 命令。" }],
  },
  {
    id: "terminal",
    name: "终端",
    summary: "持久终端会话。",
    features: [{ name: "终端", detail: "持久终端会话。宿主注入回调后，才能读、聚焦或关闭桌面窗格。" }],
  },
  {
    id: "other",
    name: "其它",
    summary: "搜索、提问和外部工具宿主。",
    features: [
      {
        name: "网页搜索",
        detail: "ddgs、brave_free、exa、tavily、firecrawl、parallel、searxng。每个提供者一个插件。",
      },
    ],
  },
  {
    id: "sandbox",
    name: "沙箱",
    summary: "同一份文件访问策略，用在文件工具和外部进程上。",
    features: [
      { name: "沙盒工具", detail: "在隔离环境中运行代码、访问文件并测试想法。" },
    ],
  },
  {
    id: "context",
    name: "上下文",
    summary: "压缩这次窗口，并算出从哪一条裁起。",
    features: [
      {
        name: "上下文压缩工具",
        detail: "智能压缩当前窗口，减少上下文占用并保留关键信息。",
      },
    ],
  },
  {
    id: "loop",
    name: "循环",
    summary: "一轮里问模型，要工具就执行，再问一次。",
    features: [
      {
        name: "linope",
        detail: "回复里没有工具调用、也没有还在跑的工具时，这一轮结束。模型和工具都走内核命令。",
      },
      {
        name: "pi",
        detail: "换上 Pi 的循环。问模型仍写 model use 和 model run，工具仍用 process start 和 load tool。",
      },
    ],
  },
  {
    id: "mcp",
    name: "MCP",
    summary: "连接外部工具服务器并调用其提供的工具。",
    features: [
      {
        name: "MCPHub",
        detail: "连接本机 MCPHub，列出并调用它正在提供的工具。",
      },
    ],
  },
];

export type { AppEntry, AppFeature, AppId };
export { APPS };
