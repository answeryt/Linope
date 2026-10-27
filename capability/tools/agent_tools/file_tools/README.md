# file_tools

English | [中文](README.cn.md)

File tools for one capability process. `load` accepts kind `tool` and a mapping. Paths are resolved by the filesystem backend the plugin calls. The room's write mode is [`kernel/environment`](../../../../kernel/environment/README.md).

| Plugin | Schema name | Role |
|---|---|---|
| `read_plugin.py` | `read` | UTF-8 text with line numbers. `offset` defaults to 1. `limit` defaults to 2000. |
| `write_plugin.py` | `write` | Create or replace a whole UTF-8 file. Requires `file_path` and `content`. |
| `edit_plugin.py` | `edit` | Replace literal `old_string` with `new_string`. Without `replace_all`, the old text must occur once. |
| `str_replace_editor_plugin.py` | `str_replace_editor` | View, create, unique literal replace, and line insert. |
| `glob_plugin.py` | `glob` | Files whose paths match a glob. |
| `grep_plugin.py` | `grep` | File contents matched by a regular expression. |
| `read_image_plugin.py` | `read_image` | PNG, JPEG, WebP, or GIF metadata for the model. |
| `file_plugin.py` | `read_file`, `write_file`, `patch`, `search_files` | Combined module. `PLUGIN_NAME` is `file_ops`. |

## Model Experience

### Tool schema

#### What the model sees

`tool_schemas()` on each plugin. Routing text that names `tools.read`, `tools.write`, `tools.edit`, `tools.glob`, and `tools.grep` is [`system_02_tools.md`](../../../prompt/prompt_card/system/system_02_tools.md).

#### Token effect

One fixed schema per visible tool, plus the returned text. `read` caps a call at `limit` lines, default 2000.

#### KV Cache effect

The schema is prefix-stable while the plugin and its visibility are unchanged. A tool result appends after that prefix.

## Known Limitations and Deferred Work

- **`read` is UTF-8 text** — a binary file is outside this plugin. Images go through `read_image`.
- **`file_ops` is a second file surface** — `file_plugin.py` is a separate plugin from the single-purpose files above.
