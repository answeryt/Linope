<p align="center">
  <img src="image.png" alt="LINOPE-KERNEL" width="720">
</p>

# Linope

English | [中文](README.zh.md)

Linope is a flexible, general, lightweight agent kernel. A model, a search tool, file handling, and context handling are capabilities. One capability is one peer process, and that process holds its own resource leases. There is no parent-child process tree.

Linope builds an agent kernel with the development ideas of a traditional operating-system kernel. As models keep being replaced, the logic and mechanisms inside many agent architectures have to change with them, which frustrates many developers. Linope aims to avoid that by maintaining a kernel that stays flexible and stable. The stable mechanisms live in the kernel, so later development is mainly maintaining that kernel.

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

Inside the window, create the secrets file, load it, then start the process. Write one variable at a time. The name is `OPENAI_API_KEY`. Put the API endpoint and model name on the start line. You can type `linope` from any directory; the launch directory is only a relative-path hint, while file and command access are resolved by `capability/sandbox`. Host scope is high privilege and should be enabled knowingly.

```text
create capability/.env -- OPENAI_API_KEY=your-api-key
load env capability/.env
process start agent_loop
```

Note the agent_loop process id. If you forget it, use the `list` command.

The runtime supplies the core model protocol automatically.

```text
load message <agent-loop-process-id> -- your message
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
