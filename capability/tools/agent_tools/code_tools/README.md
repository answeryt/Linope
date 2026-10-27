# code_tools

English | [中文](README.cn.md)

Run a Python program that calls the other agent tools.

## Contract

`run_code_plugin.py` is `PLUGIN_NAME` `run_code`. `load` accepts kind `tool`. The default timeout is 60000 milliseconds.

The program runs with a restricted builtin set: common constructors and iterators, plus `Exception`, `IndexError`, `KeyError`, `RuntimeError`, `StopIteration`, `TypeError`, and `ValueError`. Tool calls go out through the host bridge the plugin is given. This plugin does not import those tool plugins.

`capability_profile` is the process declaration for a start. Command tools are classified as `command` by [`kernel/process/profiles.py`](../../../../kernel/process/profiles.py).

## Model Experience

### Tool schema

#### What the model sees

`tool_schemas()` for `run_code`: a Python program, not a shell command. The shell tools are [`shell_tools`](../shell_tools/README.md).

#### Token effect

A fixed schema while the tool is visible. The result is the program's returned text, bounded by the timeout.

#### KV Cache effect

The schema is prefix-stable while the plugin is unchanged. The result appends.

## Known Limitations and Deferred Work

- **The builtin set is closed** — names outside the safe list are absent. File and process access go through the injected tool bridge, not through an open `os` module in the program.
