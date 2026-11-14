# tui

[English](README.md) | 中文

这个目录是蓝色终端。它画一屏，读键盘，把每一行发给内核会话。内核会话是 `python -m kernel.command session`。

## 脚本

| 脚本 | 作用 |
|---|---|
| `bin.js` | Node 的入口。它启动 `tui.launch` |
| `launch.py` | 打开这个画面，或者把其它命令交给内核 |
| `main.ts` | 正在运行的画面：按键、输入行和重画 |
| `keys.ts` | 把终端送来的字节收成一个按键 |
| `editor.ts` | 输入行、光标和命令历史 |
| `focus.ts` | 把每个按键绑到输入行或历史面板 |
| `screen.ts` | 画出一帧，并把内核事件收进对话记录 |
| `banner.ts` | 标志；窗口小时改成一行标题 |
| `theme.ts` | 这一套蓝色，以及把它们画上去的转义序列 |
| `link/session.ts` | 启动内核会话，并来回传递每一行 |
| `link/protocol.ts` | 校验一行后端 JSONL 事件 |
| `state.ts` | 把后端事实投影成画面状态 |
| `screen.check.ts` | 检查宽度、折行、滚动、滚动条和进程行 |
| `editor.check.ts` | 检查输入行、历史和按键解析 |
| `focus.check.ts` | 检查哪个按键滚动、哪个按键编辑 |
| `select.check.ts` | 检查鼠标选区、复制出来的文字，以及单击把光标放在哪 |

`bin.js` 是 Node 最先跑的文件。它把一个目录放进 `PYTHONPATH`，把 `PYTHONIOENCODING` 和 `PYTHONUTF8` 设成 UTF-8，然后用传来的参数启动 `python -m tui.launch`。设了 `LINOPE_ROOT` 时，这个目录就是它。否则用这份文件旁边的安装目录。一次启动只用这一棵树。在这份仓库里，`python -m tui.launch` 跑的是这一棵，不经过已经安装的 `linope`。已经安装的 `linope` 只代表那一份安装，除非 `LINOPE_ROOT` 指到别的目录。`LINOPE_PYTHON` 或 `PYTHON` 指定解释器。没有这两个变量时，命令就是 `python`。子进程的退出码就是本进程的退出码。

`launch.py` 看这些参数。没有参数，或者唯一的参数是 `terminal`，就打开画面。其它参数交给 `kernel.command.dispatch`，画面不打开。打开画面需要 Node.js。它用 `ui-tui/node_modules` 里的 `tsx` 跑 `tui/main.ts`。那一份不在时，改试 `npx --yes tsx`。在 Windows 上它等这个进程结束。在其它系统上，它用这个进程替换自己。

`main.ts` 是画面打开之后的那一层。在终端里，它切到备用屏幕，把窗口标题设成 `Linope`，打开 SGR 鼠标跟踪和括号粘贴，并逐个读按键。没有终端时，它按整行来读。每个按键经 `keys.ts` 进到 `focus.ts`。绑定决定这一下是改输入行，还是滚动历史，然后画面再画一次。鼠标跟踪开着时，终端自己的选区不会开始，所以在这个画面上拖动就是在选字，松开时复制。

| 按键或一行 | 发生什么 |
|---|---|
| 回车 | 把去掉首尾空白的这一行发给内核会话 |
| `/help` | 显示按键表。什么都不发送 |
| `/clear` | 清掉这个画面上的对话记录 |
| `/quit`、Ctrl-C，或空行上的 Ctrl-D | 发送 `exit`，并回到原来的屏幕 |
| Tab / Shift+Tab | 在输入行和历史面板之间切换焦点 |
| ↑ / ↓ | 在输入区里走命令历史。在历史面板里滚动一行 |
| Shift+↑ | 把历史上滚一行，并暂停跟随底部。两个焦点下都有效 |
| ← / → | 移动输入光标 |
| Home / End | 在输入区里移动光标。在历史面板里跳到顶部或底部 |
| PageUp / PageDown | 在历史面板里翻一屏 |
| 滚轮 | 指针在哪都滚动历史，焦点不动 |
| 拖动滚动条 | 拖动历史滑块。点轨道则翻一页 |
| 拖动文字 | 选中指针下的文字，松开时复制 |
| 双击 / 三击 | 复制一个词，或复制整行 |
| 右键、中键，或 Ctrl+V | 贴进输入行。粘贴里的换行变成空格 |
| 上一行还在跑 | 编辑用的按键先等着。切换焦点、滚动和复制仍然有效 |

`text-delta` 等 30 毫秒再画，这样一串小片段不会来一片画一次。其它事件马上画。跟随着时，新行留在底部。向上滚，包括 Shift+↑，会暂停跟随。再滚回底部就恢复。窗口大小变了，等 100 毫秒，尺寸确实变了再画。离开画面时把光标打开，关掉鼠标跟踪和括号粘贴，并退出备用屏幕。

`keys.ts` 是 `takeKey`。它从已经到达的字节里取出一个按键，并带上这个按键用掉的字节。普通字符、回车、退格、Tab、Ctrl-C 和 Ctrl-D 看第一个字节就能认出。方向键、Home、End、Delete、PageUp、PageDown、Shift+Tab 和 Shift+↑ 是转义序列。滚轮、鼠标按下、拖动和松开都是 SGR 鼠标序列，并带上行和列。括号粘贴是一个 `paste` 按键，从开头的 `\x1b[200~` 到结尾的 `\x1b[201~`。序列还没到齐时什么都不返回，调用方把这些字节留着。这张表里没有的序列是 `ignore`。

`editor.ts` 保管正在输入的那一行。光标是字符下标，一个汉字算一步。`insertText`、`backspace` 和 `deleteForward` 在这个下标上改字。发出去的行会记住，最多 100 条，和上一条完全相同的不再存。↑ 沿这份列表往回走，并把还没写完的一行留成草稿。↓ 往前走，走到头时把草稿放回来。移动光标或改字，就离开这次历史浏览。

`screen.ts` 拼出 `main.ts` 写到屏幕上的那一帧。

| 入口 | 做什么 |
|---|---|
| `displayWidth` | 一串文字占几列。一个汉字占两列。组合记号不占列 |
| `wrapText` | 按这个宽度折行。一行里有空格时，在空格处断开 |
| `renderScreen` | 标志、信息框、对话记录里看得见的那一段、滚动条，以及状态行 |
| `historyLayout` | 历史面板占哪些行，滚动条在哪一列 |
| `historyRoom` | 这个面板里能放几行对话 |
| `applyScroll` | 移动 `scrollY`。离开底部就暂停跟随，落回底部就恢复 |
| `followBottom` | 把面板钉在最新一行 |
| `retainScroll` | 暂停时，新行到来仍留在原地。跟随时，面板留在最新一行 |
| `scrollLimit` | 最大的 `scrollY`。零表示对话装得下 |

信息框有四项：管家在不在（`clerk` / `here`）、还活着几个进程（`alive`）、其中最近三个（`process`）、项目目录（`project`）。进程和回合状态来自带关联 id 的后端事实，不从 transcript 文本反推。`model.delta` 根据 `turn_id` 追加到对应回合，`turn.completed` 负责收束该回合。

`banner.ts` 是 `logoLines`。窗口至少有标志那么宽，并且至少有 16 行时，画出六行的 `LINOPE KERNEL` 标志。更小的窗口改成一行：横线中间写 `LINOPE-KERNEL`。

`theme.ts` 是这一套颜色：标志的蓝、边框、框底、正文、较淡的字、提示符和错误。`fg` 给文字上色，然后恢复默认。`fill` 给背景上色。`paint` 给前景上色，并把颜色留在后面的输出上。

`link/session.ts` 是 `startTerminalSession`。它在用户启动 `linope` 时的当前目录启动 `python -u -m kernel.command session`，并强制 UTF-8。解释器先用 `LINOPE_PYTHON`，再用 `PYTHON`，都没有时用 `python`。标准输出的每一行必须是 `link/protocol.ts` 接受的版本化 JSONL 事件；无帧文本只能成为协议错误，不能进入 transcript。标准错误只是诊断事件，不能成为模型回答。`send` 写出去掉首尾空白的一行。`stop` 写出 `exit`；这一写失败就杀掉进程。

`link/protocol.ts` 校验协议版本、序列、关联 id、pid 和数据记录。`state.ts` 是从这些事实到 transcript 和进程面板的纯投影；渲染器不解析命令语法或后端文本。

`screen.check.ts` 检查显示宽度、折行、滚动、reducer 投影和带关联 id 的流式收束。`link/protocol.check.ts` 检查线协议。`editor.check.ts` 检查插入、删除、历史草稿和 `takeKey`。`focus.check.ts` 检查 ↑ 在输入区里是编辑、在历史面板里是滚动，以及 Shift+↑ 在两个焦点下都是滚动。`select.check.ts` 检查拖动、双击和三击各盖住哪些格子，以及复制出来的是画面上的那些字。

用 `typescript` 包检查画面。`@types/node` 必须放在 `--typeRoots` 上；只用 `npx -p` 安装不会进入编译路径。

```text
npm install --prefix tui --no-save typescript @types/node
node tui/node_modules/typescript/bin/tsc --noEmit --pretty false --module nodenext --moduleResolution nodenext --target es2022 --skipLibCheck --typeRoots tui/node_modules/@types --types node tui/main.ts tui/state.ts tui/screen.ts tui/link/session.ts tui/link/protocol.ts
```
