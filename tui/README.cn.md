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
| `link/events.ts` | 把标准输出的一行读成一个事件 |
| `screen.check.ts` | 检查宽度、折行、滚动、滚动条和进程行 |
| `editor.check.ts` | 检查输入行、历史和按键解析 |
| `focus.check.ts` | 检查哪个按键滚动、哪个按键编辑 |

`bin.js` 是 Node 最先跑的文件。它把仓库根目录放进 `PYTHONPATH`，把 `PYTHONIOENCODING` 和 `PYTHONUTF8` 设成 UTF-8，然后用传来的参数启动 `python -m tui.launch`。`LINOPE_PYTHON` 或 `PYTHON` 指定解释器。没有这两个变量时，命令就是 `python`。子进程的退出码就是本进程的退出码。

`launch.py` 看这些参数。没有参数，或者唯一的参数是 `terminal`，就打开画面。其它参数交给 `kernel.command.dispatch`，画面不打开。打开画面需要 Node.js。它用 `ui-tui/node_modules` 里的 `tsx` 跑 `tui/main.ts`。那一份不在时，改试 `npx --yes tsx`。在 Windows 上它等这个进程结束。在其它系统上，它用这个进程替换自己。

`main.ts` 是画面打开之后的那一层。在终端里，它切到备用屏幕，把窗口标题设成 `Linope`，打开 SGR 鼠标跟踪，并逐个读按键。没有终端时，它按整行来读。每个按键经 `keys.ts` 进到 `focus.ts`。绑定决定这一下是改输入行，还是滚动历史，然后画面再画一次。

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
| 滚轮停在历史面板上 | 滚动这一块，焦点不动 |
| 上一行还在跑 | 编辑用的按键先等着。切换焦点和滚动仍然有效 |

`text-delta` 等 30 毫秒再画，这样一串小片段不会来一片画一次。其它事件马上画。跟随着时，新行留在底部。向上滚，包括 Shift+↑，会暂停跟随。再滚回底部就恢复。窗口大小变了，等 100 毫秒，尺寸确实变了再画。离开画面时把光标打开，关掉鼠标跟踪，并退出备用屏幕。

`keys.ts` 是 `takeKey`。它从已经到达的字节里取出一个按键，并带上这个按键用掉的字节。普通字符、回车、退格、Tab、Ctrl-C 和 Ctrl-D 看第一个字节就能认出。方向键、Home、End、Delete、PageUp、PageDown、Shift+Tab 和 Shift+↑ 是转义序列。滚轮是一条 SGR 鼠标序列，并带上行和列。序列还没到齐时什么都不返回，调用方把这些字节留着。这张表里没有的序列是 `ignore`。

`editor.ts` 保管正在输入的那一行。光标是字符下标，一个汉字算一步。`insertText`、`backspace` 和 `deleteForward` 在这个下标上改字。发出去的行会记住，最多 100 条，和上一条完全相同的不再存。↑ 沿这份列表往回走，并把还没写完的一行留成草稿。↓ 往前走，走到头时把草稿放回来。移动光标或改字，就离开这次历史浏览。

`screen.ts` 拼出 `main.ts` 写到屏幕上的那一帧。

| 入口 | 做什么 |
|---|---|
| `displayWidth` | 一串文字占几列。一个汉字占两列。组合记号不占列 |
| `wrapText` | 按这个宽度折行。一行里有空格时，在空格处断开 |
| `noteProcessText` | 根据 `pid=` 行，或一页 `facts` 里的 pid，更新还活着的进程 |
| `pushEvent` | 把一个内核事件收进对话记录 |
| `renderScreen` | 标志、信息框、对话记录里看得见的那一段、滚动条，以及状态行 |
| `historyLayout` | 历史面板占哪些行，滚动条在哪一列 |
| `historyRoom` | 这个面板里能放几行对话 |
| `applyScroll` | 移动 `scrollY`。离开底部就暂停跟随，落回底部就恢复 |
| `followBottom` | 把面板钉在最新一行 |
| `retainScroll` | 暂停时，新行到来仍留在原地。跟随时，面板留在最新一行 |
| `scrollLimit` | 最大的 `scrollY`。零表示对话装得下 |

信息框有四项：管家在不在（`clerk` / `here`）、还活着几个进程（`alive`）、其中最近三个（`process`）、项目目录（`project`）。一行 `pid=<编号> capability=<名字>` 把该进程记成 `waiting`。`activity=working` 记成 `busy`。`activity=sleeping` 记成 `waiting`。已关闭或已离开的进程从名单里拿掉。`text-delta` 追加到还在往外流的那条助手回复上。随后一条文字相同的 `text` 换掉这条还在流的回复。`error` 是一条错误。`image` 是一条写着 `image` 和地址的回复。

`banner.ts` 是 `logoLines`。窗口至少有标志那么宽，并且至少有 16 行时，画出六行的 `LINOPE KERNEL` 标志。更小的窗口改成一行：横线中间写 `LINOPE-KERNEL`。

`theme.ts` 是这一套颜色：标志的蓝、边框、框底、正文、较淡的字、提示符和错误。`fg` 给文字上色，然后恢复默认。`fill` 给背景上色。`paint` 给前景上色，并把颜色留在后面的输出上。

`link/session.ts` 是 `startTerminalSession`。它在仓库根目录启动 `python -u -m kernel.command session`，并强制 UTF-8。根目录是含有 `kernel/command/__main__.py` 的那一层。标准输出的每一行都交给 `parseEvent`。不是这些事件的一行，就按普通文字显示。标准错误凑齐一行后，作为一条错误送出。会话开始时先送一个 `session` 事件，里面带着当前目录。进程关掉时，画面先听到 `left`，再听到 `done`。`send` 写出去掉首尾空白的一行。进程已经不在时，画面听到 `The clerk has left`。`stop` 写出 `exit`；这一写失败就杀掉进程。

`link/events.ts` 是 `parseEvent`。不是以 `{` 开头的一行，就不是事件。带 `type` 的 JSON 对象会变成 `done`、`image`、`session`、`text`、`text-delta`、`status` 或 `error` 中的一种。没有 `href` 的 `image`，以及解析不了的 JSON，会被丢掉。

`screen.check.ts` 检查显示宽度、折行、滚动位置能看到长对话的哪一段、滚动条何时出现、跟随如何暂停和恢复、流式文字如何收成一条助手回复，以及 `pid=` 行如何更新进程名单。`editor.check.ts` 检查插入、删除、历史草稿和 `takeKey`。`focus.check.ts` 检查 ↑ 在输入区里是编辑、在历史面板里是滚动，以及 Shift+↑ 在两个焦点下都是滚动。
