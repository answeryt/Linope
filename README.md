<p align="center">
  <img src="image.png" alt="LINOPE-KERNEL" width="720">
</p>

# Linope

English | [中文](README.zh.md)

Linope is an agent kernel. Models, tools, and context handling are capabilities scheduled by the kernel, rather than steps written into one agent instance.

The basic relation is **agent = kernel + capabilities**. One capability is one peer process, and that process holds its own resource leases. The kernel manages process lifetime, resources, permission, and communication between processes. The model chooses among the capabilities that are still available on the current page.

The kernel manages four agent resources: `memory`, `tool`, `sandbox`, and `network`. The CPU, disk, and network devices remain with the host operating system.

## Current status

Linope is still under development, at version `0.0.1`. Commands, resource records, and page format may change.

## Run

Python 3.11 or newer is required. Linope terminal also requires Node.js 20 or newer.

### Run from source

```sh
git clone https://github.com/answeryt/Linope.git
cd Linope
pip install -e .
```

Open the terminal on Windows:

```powershell
.\linope.cmd terminal
```

On other systems:

```sh
node tui/bin.js terminal
```

Inside the window, point at the secrets file, then start the capability processes. The smallest search example is [example/README.md](example/README.md).

```text
load env capability/.env
process start model.openai_chat_model --with memory=search
process start tools.ddgs
```

`tools.ddgs` uses the separately installed [`ddgs`](https://pypi.org/project/ddgs/) package. A model process reads only the secret name written on its own card from `capability/.env`, such as `OPENAI_API_KEY`.

## Documentation

| Document | Contents |
|---|---|
| [kernel/README.md](kernel/README.md) | Processes, resources, scheduling, and commands |
| [capability/README.md](capability/README.md) | Model and tool plugins |
| [tui/README.md](tui/README.md) | The blue terminal |
| [example/README.md](example/README.md) | One model process and one search process |
