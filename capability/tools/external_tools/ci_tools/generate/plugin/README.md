# plugin

English | [中文](README.cn.md)

Plugin-convention CI: review whether plugin families in the repository are atomic, isolated, and entered correctly, and generate the allow and deny lists.

The host is the composition layer, not a check. It loads `*_check.py` / `*_generate.py` by file name with importlib (the same way pypyr loads a step by name). It does not statically import each plugin.

## Place

- Scan scope: the Open-Linux repository root (it sees both `kernel/` and `capability/`). Skip caches, dot directories, `*-main` third-party trees, nested SDKs and reference implementations (`temporal-sdk-python`, `restate-sdk-python`, `temporal`, `restate`), and test directories. A new plugin root does not require a host change. The default `--root` walks to the directory that contains `kernel/compose/capability/composition.yaml`.
- Review: each `*_check.py` shares one context and only appends violations to `violations`.
- Generate: each `*_generate.py` writes a list card for `--format` (json / yaml / toml / md).
- The only hand-written list is the allow list. The deny list is the discovered families minus the allow paths.
- `--check`: fail when a committed list card is stale, or when a violation has `severity=error`.

## Packages to install

These are third-party PyPI packages, not imports between modules in the repository. CI only parses source statically and does not import them. Install them to run the review, or to load the vendored `sphinxext`.

| Package | Use | Who uses it |
| --- | --- | --- |
| `PyYAML` | Read the host `composition.yaml` and list cards | `host_sibling/lip_check.py`, the allow and deny generators |
| `sphinx` | Sphinx documentation engine (also installs `sphinxcontrib-*`, `alabaster`, `babel`, and others) | `kernel/compose/plugin/vendor/stevedore/src/stevedore/sphinxext.py` |
| `docutils` | reStructuredText parsing (a dependency of `sphinx`) | The same file: `nodes` / `rst` / `directives` / `StringList` |

```text
python -m pip install PyYAML sphinx docutils
```

`from sphinx ...` / `from docutils ...` at the top of `sphinxext.py` are third-party dependencies of the documentation extension. `from stevedore import extension` is a reference inside the vendored package. A leaf plugin still must not import `stevedore`. If you are not writing a Sphinx plugin list, you do not need to install `sphinx`.

## Layout

```text
plugin/
  plugin_generate.py          Host
  README.md
  list/
    deny_list/                default constraints + deny card generation
      deny_check.py
      deny_list_generate.py
      deny_list_crad/list.*
    allow_list/               hand-written exemptions + allow card generation
      allow_check.py
      allow_list_generate.py
      allow_list_card/list.*
    host_sibling/             infer the contract from the family shape on disk
      surface_check.py
      sdk_boundary_check.py
      provider_config_check.py
      kernel_check.py
      lip_check.py
      assembly_check.py
      descriptor_check.py
```

## Files

| File | Plugin name | Role |
| --- | --- | --- |
| `plugin_generate.py` | `plugin_generate_host` | Discover families, split deny/allow, load and run plugins |
| `list/deny_list/deny_check.py` | `plugin_deny` | A facade must not be an aggregation layer; no imports across plugins or sibling files |
| `list/deny_list/deny_list_generate.py` | `plugin_deny_generate` | Write the deny list card |
| `list/allow_list/allow_check.py` | `plugin_allow` | Pardon `.gates` isolation edges; check required injected parameters |
| `list/allow_list/allow_list_generate.py` | `plugin_allow_generate` | Read and write the hand-written allow list card |
| `host_sibling/surface_check.py` | `plugin_surface` | Infer the entry contract from the file shape |
| `host_sibling/sdk_boundary_check.py` | `plugin_sdk_boundary` | The `call_api` family lazy-loads the SDK. Message formatting, response parsing, and window-recovery retry live in the leaf. Tool-schema conversion is forbidden |
| `host_sibling/provider_config_check.py` | `plugin_provider_config` | A provider card is one JSON file and must not be used as code |
| `host_sibling/kernel_check.py` | `plugin_kernel` | Kernel layers, ProcessRun/Activation, and the OS/deployment boundary. Architecture vocabulary and the structure tree are in each layer's generator |
| `host_sibling/lip_check.py` | `plugin_lip` | Socket paths: `sockets` / `modules` / `sources` in `composition.yaml`. A leaf plugin must not import pluggy/stevedore/lip |
| `host_sibling/assembly_check.py` | `plugin_assembly` | Capability-graph path: a composer may only wire things together. It must use a compose Source. `register_adapter` must connect directly to `FunctionModelAdapter`. Hand-written discover, kind translation, capability-prefix scans, and dynamic dispatch after reflecting members are forbidden |
| `host_sibling/descriptor_check.py` | `plugin_descriptor` | A leaf `CAPABILITY` / `MODEL_CAPABILITY` and the open-cluster kind, requires, and entry in `plugin.json` |

## Review rules

### deny: atomic and isolated

- `facade.filename`: a family must not contain `host.py` / `facade.py`
- `facade.barrel_init`: `__init__.py` must not re-export sibling plugins
- `isolation.sibling_import`: do not import another plugin file in the same family
- `isolation.cross_plugin_import` / `isolation.project_import`: do not import another project's plugin
- The standard library, and third-party imports that cannot be resolved to a file in the repository, are allowed. Explicit exceptions go in the allow list

### allow: exemptions and injection

- `paths`: these paths do not enter the generated deny list (including the socket engine `kernel/compose/plugin` and the capability-graph engine `kernel/compose/capability`)
- Edges in `.gates/isolation-allowlist.json`: after deny finishes, pardon the matching isolation violations
- `inject`: parameters a named stem must receive (for example `sandbox_policy` must inject `canonical_path`), so a plugin does not import a sibling implementation
- `kernel_layers`: the kernel structure inventory, read by `kernel_check`
- `sockets`: socket name to plug name to leaf plugin path, read by `lip_check`. The host loads by name. A leaf plugin must not import an implementation
- `injection.estimator_param`: error when a required injected parameter is missing

### host_sibling: the contract is inferred from disk, not a hard-coded host kind table

| Shape | Requirement |
| --- | --- |
| `*_plugin.py` | `PLUGIN_NAME`, `PLUGIN_VERSION`. `PLUGIN_NAME` is globally unique |
| `*_check.py` / `*_generate.py` | `PLUGIN_NAME`, `PLUGIN_VERSION`, `run(context)` |
| family already has `call_api` | every module exposes `call_api` |
| family already has `apply_*` | the module exposes `apply_*`. Model request fields live in the matching `model_interface` file, not one file per field |
| other | at least one public function or class |

Extra constraints for a family that already has `call_api`:

- A provider SDK (`openai` / `anthropic` / `google` / `genai`) must be imported inside `call_api`, not at module top level
- Message formatting, response parsing, and context-window recovery retry live in the matching leaf (`format_messages` / `parse_response` / `parse_stream_chunk`; retry is inside `call_api`)
- Do not provide a tool-schema conversion helper such as `convert_tools` / `tool_choice_convert`

For a family that looks like a provider root: each provider subdirectory has one `<name>.json` card. The top-level keys `provider` / `interface` / `model` / `api_key_env` / `parameters` are present. `interface` must correspond to `model/model_API/model_interface/<interface>.py`.

`kernel_check.py` constrains `kernel/`: the top level may contain only layers declared by the allow card; plugins sit in leaf directories; a ProcessRun must include the process/run id, definition version, state, Activation, and resource leases; an Activation must be serializable; the Process/Task/Resource layers must not use OS process/thread or deployment APIs. `kernel/compose/plugin/` is the socket engine (pluggy / stevedore / lip) and is not checked for OS or deployment imports.

Do not mix the two assembly paths:

- Socket path: `sockets` / `modules` / `sources` in `kernel/compose/capability/composition.yaml`, reviewed by `lip_check.py`.
- Capability-graph path: `ComposeSpec` plus Sources, reviewed by `assembly_check.py`. Leaf descriptors are reviewed by `descriptor_check.py`.

`lip_check.py` constrains capability lookup: a `sockets` entry in the composition must point at a plug file that exists, and `PLUGIN_NAME` inside that file must match the plug name. `*_plugin.py`, the host `manager/lip/board.py`, and other non-engine family files must not import `pluggy` / `stevedore` / `lip`. The socket board is a local fork of `manager/stevedore` (relative imports inside the package). The host loads only by file path. Imports across plugin files are still deny_check's job. If `sources` is present, `type` must be recognized by `source_from_mapping`.

`assembly_check.py` constrains capability-graph assembly: a file that imports `CapabilityCatalog` / `CapabilityGraphResolver` / `ComposeSpec` and is not under `kernel/compose/` or `tests/kernel/` is a composer. A composer must use `inject` / `inject_capabilities` / `CapBus` / `Capability`. It must not `ast.parse`, must not write its own `discover()`, must not write another kind-translation table, and must not scan by capability prefix. When `FunctionModelAdapter` is not used, it must not `inspect.signature` and must not duck-type a fallback across four ABIs. `register_adapter` must connect directly to `FunctionModelAdapter` (it cannot wrap a layer and then register). It must not reflect leaf call details through `vars/dir/getmembers + startswith + dynamic call`.

This rule is a general role boundary, not a special case for models: a composer should only assemble. It should not shape requests, orchestrate retries, or dispatch by reflection.

`descriptor_check.py` constrains open-cluster descriptors: `kind` is a cluster the plugin declares itself (it may be refined with dots), not a kernel allow-list. `name` or `provides` must fall under that cluster. `requires` uses the same syntax as kernel `parse_requirements`. `entry` must point at a function that exists. Old loader words (`recipe` / `module` / `tool` / `model`) must not be used as `kind` again.

## Generated lists

The allow list is the only hand-written inventory. Fields:

- `paths`: exempt paths
- `inject`: stem to required injected parameter names (including kernel plugins)
- `kernel_layers`: hand-written inventory, read by `kernel_check` through `load()`
- `sockets`: hand-written inventory, read by `lip_check`. The host loads a leaf plugin by socket name and plug name

The deny list is generated from the host's discovery result minus the allow paths. Fields:

- `families`: root paths of plugin families under the default constraints

`--check` does not write files. It only compares committed cards for staleness. Stale paths are recorded in `stale`.

## Call path

```text
python plugin_generate.py [--check] [--format json|yaml|toml|md] [--root ...]

plugin_generate.py (Host)
  → discover families from disk and split denied / allowed with the allow list
  → review: deny_check → allow_check → surface / sdk_boundary / provider_config / kernel_check / lip_check / assembly_check / descriptor_check
  → generate: allow_list_generate → deny_list_generate
  → --check: stale or an error violation → exit 1
  → default: write the list cards; if an error violation remains → exit 1
```

Plugin convention: each `*_check.py` / `*_generate.py` exposes `PLUGIN_NAME`, `PLUGIN_VERSION`, and `run(context)`. The host passes the same context through in order. A check only appends `violations`. A generator only writes cards.

## Design

The host, review, and generation are separate. The host only discovers and orchestrates. A check does not write files. A generator does not judge isolation. The allow list is written by hand and the deny list is automatic. A new plugin family enters the constraints by default and leaves the deny list only with an explicit exemption.

## Known Limitations and Deferred Work

- **Default root uses a marker this tree does not have** — `find_repo_root` looks for `.gates/isolation-allowlist.json`, top-level `model/` and `tools/`, and `kernel/compose/capability`. Those paths are absent here, so the function falls back to six parents above this file.
- **`sphinx` is named for a vendored extension path** — `kernel/compose/plugin/vendor/stevedore` is not in this tree. Install `sphinx` only when that extension is present. `PyYAML` is what the list cards need.
