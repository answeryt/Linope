# tui

English | [中文](README.cn.md)

This directory is the blue terminal. It draws one screen, reads the keyboard, and sends each line to the kernel session. The kernel session is `python -m kernel.command session`.

## Scripts

| Script | Role |
|---|---|
| `bin.js` | The Node entry. It starts `tui.launch` |
| `launch.py` | Opens this screen, or hands any other command to the kernel |
| `main.ts` | The running screen: keys, the input line, and redraws |
| `keys.ts` | Turns the bytes from the terminal into one key |
| `editor.ts` | The input line, the cursor, and the command history |
| `focus.ts` | Binds each key to the input line or the history pane |
| `screen.ts` | Paints one frame and folds kernel events into the transcript |
| `banner.ts` | The logo, or a short title when the window is small |
| `theme.ts` | The blues, and the sequences that paint them |
| `link/session.ts` | Starts the kernel session and carries lines both ways |
| `link/protocol.ts` | Validates one backend JSONL event |
| `state.ts` | Projects backend facts into screen state |
| `screen.check.ts` | Checks width, wrapping, scrolling, the scrollbar, and process lines |
| `editor.check.ts` | Checks the input line, the history, and key parsing |
| `focus.check.ts` | Checks which key scrolls and which key edits |
| `select.check.ts` | Checks mouse selection, the copied text, and where a click places the cursor |

`bin.js` is what Node runs first. It puts one directory on `PYTHONPATH`, sets `PYTHONIOENCODING` and `PYTHONUTF8` to UTF-8, and starts `python -m tui.launch` with the arguments it was given. `LINOPE_ROOT` is that directory when it is set. Otherwise the directory is the install next to this file. One launch uses that one tree. Inside this checkout, `python -m tui.launch` runs this tree and does not go through an installed `linope`. An installed `linope` is that install, unless `LINOPE_ROOT` names another directory. `LINOPE_PYTHON` or `PYTHON` names the interpreter. Otherwise the command is `python`. The child's exit code is this process's exit code.

`launch.py` looks at those arguments. No arguments, or the single argument `terminal`, opens the screen. Any other arguments go to `kernel.command.dispatch` and this screen stays closed. Opening the screen needs Node.js. It runs `tui/main.ts` with the `tsx` installed under `ui-tui/node_modules`. When that copy is missing, it tries `npx --yes tsx`. On Windows it waits for that process. Elsewhere it replaces this process with it.

`main.ts` is the screen while it is open. On a terminal it switches to the alternate screen, sets the window title to `Linope`, turns on SGR mouse tracking and bracketed paste, and reads keys one by one. Without a terminal it reads whole lines. Each key goes through `keys.ts` into `focus.ts`. The binding edits the input or scrolls the history, then the frame is drawn again. Mouse tracking keeps the terminal from starting its own selection, so a drag on this screen selects the text itself and copies it on release.

| Key or line | What happens |
|---|---|
| Enter | Sends the trimmed line to the kernel session |
| `/help` | Shows the key list. Nothing is sent |
| `/clear` | Clears the transcript on this screen |
| `/quit`, Ctrl-C, or Ctrl-D on an empty line | Sends `exit` and restores the previous screen |
| Tab / Shift+Tab | Moves focus between the input line and the history pane |
| ↑ / ↓ | In the input, walks the command history. In the history pane, scrolls one line |
| Shift+↑ | Scrolls the history up one line and pauses following the bottom. This works from either focus |
| ← / → | Moves the input cursor |
| Home / End | In the input, moves the cursor. In the history pane, jumps to the top or the bottom |
| PageUp / PageDown | In the history pane, moves one page |
| Wheel | Scrolls the history wherever the pointer is, and does not move focus |
| Drag the scrollbar | Drags the history thumb. A click on the track moves one page |
| Drag | Selects the text under the pointer and copies it when you release |
| Double-click / triple-click | Copies the word, or the whole line |
| Right-click, middle-click, or Ctrl+V | Pastes into the input line. A newline in the paste becomes a space |
| A line that is still running | Editing keys wait. Focus, scrolling, and copying still work |

A `text-delta` redraws after 30 milliseconds, so a stream of small pieces does not paint once per piece. Any other event paints immediately. New lines stay at the bottom while follow is on. Scrolling up, including Shift+↑, pauses follow. Reaching the bottom again turns it back on. A window resize paints again after 100 milliseconds when the size actually changed. Leaving the screen turns the cursor back on, turns mouse tracking and bracketed paste off, and leaves the alternate screen.

`keys.ts` is `takeKey`. It takes the bytes waiting in the input and returns one key plus the bytes that key used. A plain character, Enter, Backspace, Tab, Ctrl-C, and Ctrl-D are recognized on the first byte. Arrows, Home, End, Delete, PageUp, PageDown, Shift+Tab, and Shift+Up arrive as escape sequences. A wheel movement, a mouse press, a drag, and a release arrive as SGR mouse sequences and carry the row and column. Bracketed paste arrives as one `paste` key, from the opening `\x1b[200~` through the closing `\x1b[201~`. A sequence that has not finished yet returns nothing, and the caller keeps the bytes. A sequence this table does not name is `ignore`.

`editor.ts` keeps the line you are typing. The cursor is a character index, so a Chinese character counts as one step. `insertText`, `backspace`, and `deleteForward` edit at that index. Submitted lines are remembered, up to 100, and a line that repeats the previous one is not stored twice. ↑ walks back through that list and keeps the unfinished line as a draft. ↓ walks forward and, at the end, puts the draft back. Moving the cursor or editing leaves the history walk.

`screen.ts` builds the frame `main.ts` writes.

| Entry | What it does |
|---|---|
| `displayWidth` | The columns one string takes. A Chinese character takes two. A combining mark takes none |
| `wrapText` | Breaks text to that width, at spaces when a line has them |
| `renderScreen` | The logo, the info box, the visible part of the transcript, the scrollbar, and the status line |
| `historyLayout` | The history pane's rows and the column that holds the scrollbar |
| `historyRoom` | How many transcript rows fit in that pane |
| `applyScroll` | Moves `scrollY`. Leaving the bottom pauses follow. Landing on the bottom resumes it |
| `followBottom` | Pins the pane to the newest line |
| `retainScroll` | Keeps a paused pane in place when new lines arrive. A following pane stays on the newest line |
| `scrollLimit` | The largest `scrollY`. Zero means the transcript fits |

The info box shows four fields: whether the clerk is here (`clerk` / `here`), how many processes are alive (`alive`), the last three of those processes (`process`), and the project directory (`project`). Process and turn state comes from correlated backend events; no transcript text is parsed to reconstruct it. A `model.delta` appends to the turn identified by `turn_id`, and `turn.completed` finalizes it.

`banner.ts` is `logoLines`. When the window is at least as wide as the block logo and at least 16 rows tall, it draws the six-line `LINOPE KERNEL` logo. A smaller window gets one line, `LINOPE-KERNEL`, between rules.

`theme.ts` is the palette: logo blues, the border, the box fill, the text, the muted text, the prompt, and errors. `fg` paints text and then resets. `fill` paints the background. `paint` paints the foreground and leaves the color on.

`link/session.ts` is `startTerminalSession`. It starts `python -u -m kernel.command session` in the directory where `linope` was started, with UTF-8 forced on. The interpreter is `LINOPE_PYTHON`, then `PYTHON`, then `python`. Every stdout line must be a versioned JSONL event accepted by `link/protocol.ts`; an unframed line is a protocol error, never transcript text. Stderr is a diagnostic event and never a model answer. `send` writes one trimmed line. `stop` writes `exit`, and kills the process when that write fails.

`link/protocol.ts` validates the wire version, sequence, correlation ids, pid and data record. `state.ts` is the pure projection from those facts to the transcript and process panel. Rendering does not inspect command syntax or backend payload text.

`screen.check.ts` checks display width, wrapping, scrolling, reducer projection and correlated stream completion. `link/protocol.check.ts` checks wire validation. `editor.check.ts` checks inserting, deleting, the history draft, and `takeKey`. `focus.check.ts` checks that ↑ edits from the input, scrolls from the history pane, and that Shift+↑ scrolls from either focus. `select.check.ts` checks which cells a drag, a double-click, and a triple-click cover, and that the copied words are the ones on screen.

Typecheck the screen with the `typescript` package. `@types/node` has to be on `--typeRoots`; installing it with `npx -p` does not put it on the compilation path.

```text
npm install --prefix tui --no-save typescript @types/node
node tui/node_modules/typescript/bin/tsc --noEmit --pretty false --module nodenext --moduleResolution nodenext --target es2022 --skipLibCheck --typeRoots tui/node_modules/@types --types node tui/main.ts tui/state.ts tui/screen.ts tui/link/session.ts tui/link/protocol.ts
```
