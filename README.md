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

## Configure the Model and API Endpoint

This example starts `model.openai_chat_model`, which uses an OpenAI Chat-compatible interface. The model name and API endpoint are defined in this card:

```text
capability/model/model_provider/openai_chat_model/openai_chat_model.json
```

The main fields to change are:

```json
{
  "model": "deepseek-flash",
  "base_url": "https://api.deepseek.com"
}
```

These are the current defaults. When changing providers, set `model` to the model id provided by the provider and `base_url` to its API endpoint. Do not assume that the endpoint ends in `/v1`; follow the provider's documentation. `api_key_env` is the environment-variable name and defaults to `OPENAI_API_KEY`; it usually does not need to change.

Note that the current implementation reads the card JSON and the matching plugin's `CARD_CONFIG` for different parts of the process. When changing the model or `base_url`, update both of these files:

```text
capability/model/model_provider/openai_chat_model/openai_chat_model_plugin.py
```

Keep `model`, `base_url`, and `api_key_env` consistent in both files. If you use the Responses interface, make the corresponding changes in:

```text
capability/model/model_provider/openai_response_model/openai_response_model.json
capability/model/model_provider/openai_response_model/openai_response_model_plugin.py
```

## Create Environment Variables

Environment variables are stored in:

```text
capability/.env
```

Create this file in the repository root if it does not exist. Put one variable on each line, for example:

```dotenv
OPENAI_API_KEY=your-api-key
```

The variable name must match `api_key_env` in the model card. After entering the Linope terminal, run this first:

```text
load env capability/.env
```

Then start the model and tool processes. This file contains secrets. Do not put real keys in documentation, commit them to Git, or share them with other people.

## Learn the Command Line

The complete command rules are documented here:

- [Chinese command rules](example/linope.cn.md)
- [English command rules](example/linope.md)

[The example guide](example/README.md) demonstrates the full sequence: starting the model, starting the search tool, registering a service, and sending a question.

After starting a model process with `memory`, load one of the command guides into its system memory:

```text
load message <model-process-id> -- example/linope.md
```

For a model using Chinese instructions, load:

```text
load message <model-process-id> -- example/linope.cn.md
```

This teaches the model Linope's command protocol, page format, and safety boundaries. It can then choose and combine available capabilities from the current page more independently, instead of requiring a person to spell out every command. Loading the guide does not grant additional permissions; the model can still execute only the commands available on the current page.

Directory notes:

| Document | Contents |
|---|---|
| [kernel/README.md](kernel/README.md) | Processes, resources, scheduling, and commands |
| [capability/README.md](capability/README.md) | Model and tool plugins |
| [tui/README.md](tui/README.md) | Linope terminal |
| [example/README.md](example/README.md) | One model process and one search process |

If you find the design philosophy behind this project interesting or inspiring, please consider giving it a star, opening an issue, or submitting a PR.

You’re also welcome to share the Linope project or its technical report on other platforms. Thank you for helping spread the word!
