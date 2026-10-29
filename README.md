<p align="center">
  <img src="image.png" alt="LINOPE-KERNEL" width="720">
</p>

# Linope

English | [中文](README.zh.md)

Linope is an agent kernel. A model, a search tool, file handling, and context handling are capabilities. One capability is one peer process, and that process holds its own resource leases. There is no parent-child process tree.

The kernel creates and reclaims these processes, checks permission, and passes requests between them. Whether to search, read a file, or answer directly is the model's choice from the current page. The kernel does not contain one agent's business workflow.

The same kernel can do different work when the model, tools, prompts, and permissions change. The kernel manages four agent resources: `memory`, `tool`, `sandbox`, and `network`. The CPU, disk, and network devices remain with the host operating system.

[The technical report](<linope-agent-kernel (2).pdf>) explains why a capability is a process, why there is no parent-child process tree, and how memory and pages fit together.

The parts that have not yet been tested in a real environment are listed in [Current Status](status.md).

If you want to learn Linope's command line, read the [command-line documentation](kernel/command/README.md).

## Quick start

Python 3.11 or newer is required. Linope terminal also requires Node.js 20 or newer.

```sh
pip install linope
linope
```

After it is installed, the next time you use it, type `linope` in the terminal.

## Create an Environment Variable and Send a Message

Inside the window, create the secrets file, load it, then start the process. Write one variable at a time. The name is `OPENAI_API_KEY`. Put the API endpoint and model name on the start line.

```text
create capability/.env -- OPENAI_API_KEY=your-api-key
load env capability/.env
process start model.openai_chat_model --change base_url=https://your-api-endpoint --change model=your-model --with memory=search
```

A process that is already running keeps its old endpoint and model until you `process start` again.

Note the model process id. If you forget it, use the `list` command.

Load [example/linope.md](example/linope.md) into that model:

```text
load message <model-process-id> -- example/linope.md
```

Then send a message with the same command:

```text
load message <model-process-id> -- your message
```

Directory notes:

| Document | Contents |
|---|---|
| [kernel/README.md](kernel/README.md) | Processes, resources, scheduling, and commands |
| [capability/README.md](capability/README.md) | Model and tool plugins |
| [tui/README.md](tui/README.md) | Linope terminal |
| [example/README.md](example/README.md) | One model process and one search process |

If you find the design philosophy behind this project interesting or inspiring, please consider giving it a star, opening an issue, or submitting a PR.

You’re also welcome to share the Linope project or its technical report on other platforms. Thank you for helping spread the word!
