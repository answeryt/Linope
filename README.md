<p align="center">
  <img src="image.png" alt="LINOPE-KERNEL" width="720">
</p>

# Linope

English | [中文](README.zh.md)

Linope is an agent kernel. A model, a search tool, file handling, and context handling are capabilities. One capability is one peer process, and that process holds its own resource leases. There is no parent-child process tree.

The kernel creates and reclaims these processes, checks permission, and passes requests between them. Whether to search, read a file, or answer directly is the model's choice from the current page. The kernel does not contain one agent's business workflow.

The same kernel can do different work when the model, tools, prompts, and permissions change. The kernel manages four agent resources: `memory`, `tool`, `sandbox`, and `network`. The CPU, disk, and network devices remain with the host operating system.

## Quick start

Python 3.11 or newer is required. Linope terminal also requires Node.js 20 or newer.

```sh
git clone https://github.com/answeryt/Linope.git
cd Linope
pip install .
```

That install includes the model SDKs, `litellm`, `ddgs`, and `mcp`. Then type:

```sh
linope
```

On Windows the command comes from that Python's `Scripts` directory. If the shell cannot find `linope`, run `.\linope.cmd` from the repository.

Inside the window, point at the secrets file, then start the capability processes. The smallest search example is [example/README.md](example/README.md).

```text
load env capability/.env
process start model.openai_chat_model --with memory=search
process start tools.ddgs
```

A model process reads only the secret name written on its own card from `capability/.env`, such as `OPENAI_API_KEY`.

## Design

[The technical report](linope_technical_report.md) explains why a capability is a process, why there is no parent-child process tree, and how memory and pages fit together.

Directory notes:

| Document | Contents |
|---|---|
| [kernel/README.md](kernel/README.md) | Processes, resources, scheduling, and commands |
| [capability/README.md](capability/README.md) | Model and tool plugins |
| [tui/README.md](tui/README.md) | The blue terminal |
| [example/README.md](example/README.md) | One model process and one search process |
