"""编码上下文感知——Hermes 基础能力，覆盖所有交互界面。

当用户在代码工作区中运行 Hermes（CLI、TUI、桌面应用，或通过 ACP
连接的编辑器）时，Hermes 会切换到 **编码姿态（coding posture）**。
本模块是唯一决定当前是否处于该姿态及其含义的地方，
代码库其余部分无需自行重复判断「是否在编码」。

架构——单一接缝，多处消费
----------------------------------------
姿态建模为从小型 :class:`ContextProfile` 注册表（当前含 ``coding`` 与
``general``）中选出的不可变 :class:`RuntimeMode`。profile 是 *数据*——
声明要收缩到的 toolset、要注入的操作简报，以及面向其他域的提示
（模型路由、记忆、子智能体）。各域读取同一解析结果，而非自行探测
git/配置：

  * **System prompt** — ``RuntimeMode.system_blocks()`` → 操作简报 +
    实时 git/工作区快照（``agent/system_prompt.py``）。
  * **Toolset** — ``RuntimeMode.toolset_selection()`` → ``coding`` toolset
    加用户已启用的 MCP 服务器（``cli.py`` / ``tui_gateway``）。仅在
    显式 opt-in 的 ``focus`` 模式下：默认姿态仅改提示词，
    不触碰用户已配置的 toolset（消息/智能家居/音乐等 toolset 本即
    默认关闭；显式启用了 image-gen 或 Spotify 的用户不应因在 git
    仓库中而失去它们）。
  * **Delegation** — 子智能体继承父级 toolset，经同一 prompt builder
    运行，编码姿态可免费传播到子级。
  * **Model / memory / compression** — 在 profile 上声明
    （``model_hint``、``memory_policy``）作为扩展接缝；消费者读取
    ``mode.profile``，而非重新决策。

缓存安全
------------
模式 **一次** 解析后即不可变。工作区快照在构建提示词时生成一次，
并烘焙进 *stable* 系统提示词层——不在每轮重新探测（否则会破坏
提示词缓存）。分支与 dirty 状态会在会话中途漂移，因此简报要求模型
在依据快照行动前用 ``git`` 重新核对。``/coding`` 切换因此仅在
下一会话生效（延迟），与 ``/skills install`` 对比 ``--now`` 的
约定相同。

激活方式（配置 ``agent.coding_context``）：

  * ``auto``（默认）——在位于代码工作区（git 仓库或识别的项目根）
    的交互式编码界面上启用姿态（简报 + 快照）。仅提示词；
    toolset 与 skill 索引不变。
  * ``focus``——同 ``auto``，但额外将 toolset 收缩为
    ``coding`` 集 + 已启用 MCP 服务器，并在提示词 skill 索引中将
    非编码 skill 类别降为仅名称（永不隐藏任何 skill）。
    显式 opt-in 以获得精简 schema。
  * ``on``——在任何位置强制启用姿态（含非工作区）。仅提示词。
  * ``off``——完全禁用。
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from hermes_cli._subprocess_compat import bounded_git_probe

logger = logging.getLogger("hermes.coding_context")

CODING_TOOLSET = "coding"

# Surfaces where a coding posture makes sense under ``auto``. Messaging
# platforms (telegram, discord, slack, …) are intentionally absent — a chat bot
# in a group is not pair-programming.
INTERACTIVE_CODING_PLATFORMS = {"cli", "tui", "acp", "desktop", ""}

# Project-root signals that mark a directory as a code workspace even when it
# isn't (yet) a git repo. Cheap filename checks — no parsing.
_PROJECT_MARKERS = (
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "package.json", "tsconfig.json", "deno.json",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "Gemfile", "composer.json", "mix.exs", "pubspec.yaml",
    "CMakeLists.txt", "Makefile", "Dockerfile",
    "AGENTS.md", "CLAUDE.md", ".cursorrules",
)

# Agent-instruction files surfaced separately from manifests in the snapshot.
_CONTEXT_FILES = ("AGENTS.md", "CLAUDE.md", ".cursorrules")

# Source-file extensions that make a git repo a *code* workspace even with no
# manifest. Without this, `git init` on a notes/writing/research folder (a huge
# non-coding use case) would flip the whole session into the coding posture just
# for having a `.git`. A manifest still wins on its own (see `_PROJECT_MARKERS`).
_CODE_EXTENSIONS = frozenset({
    ".py", ".pyi", ".ipynb", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".kts", ".scala", ".rb", ".php", ".c", ".h",
    ".cc", ".cpp", ".hpp", ".cs", ".swift", ".m", ".mm", ".dart", ".ex", ".exs",
    ".lua", ".sh", ".bash", ".zsh", ".sql", ".vue", ".svelte", ".r", ".jl",
    ".hs", ".clj", ".erl", ".pl",
})

# Dirs never worth scanning for the code check (deps/build/vcs/venv noise).
_CODE_SCAN_SKIP_DIRS = frozenset({
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    "target", ".next", ".turbo", "vendor",
})

# Bounded sweep: a code workspace reveals itself in the first handful of entries.
_CODE_SCAN_MAX_ENTRIES = 500


def _has_code_files(root: Path) -> bool:
    """Cheap, bounded check for source files in a repo's top two levels.

    Lets a git repo of loose scripts (no manifest) still read as a code
    workspace while a bare notes/writing repo does not. Scans the root and its
    immediate subdirectories only, capped at ``_CODE_SCAN_MAX_ENTRIES`` stats —
    a handful of readdirs at session start, not a full walk.
    """
    seen = 0
    stack = [(root, True)]
    while stack:
        directory, is_root = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    seen += 1
                    if seen > _CODE_SCAN_MAX_ENTRIES:
                        return False
                    name = entry.name
                    try:
                        if entry.is_file():
                            if os.path.splitext(name)[1].lower() in _CODE_EXTENSIONS:
                                return True
                        elif is_root and entry.is_dir() and name not in _CODE_SCAN_SKIP_DIRS and not name.startswith("."):
                            stack.append((Path(entry.path), False))
                    except OSError:
                        continue
        except OSError:
            continue
    return False

# Lockfile → package manager, checked in priority order.
_PY_LOCKFILES = (("uv.lock", "uv"), ("poetry.lock", "poetry"), ("Pipfile.lock", "pipenv"))
_JS_LOCKFILES = (
    ("pnpm-lock.yaml", "pnpm"), ("bun.lockb", "bun"), ("bun.lock", "bun"),
    ("yarn.lock", "yarn"), ("package-lock.json", "npm"),
)

# package.json scripts / Makefile targets worth surfacing as verify commands.
_VERIFY_TARGETS = ("test", "tests", "lint", "typecheck", "check", "build", "fmt", "format")
_MAX_VERIFY_COMMANDS = 8
_MAX_FACT_FILE_BYTES = 256 * 1024

_GIT_TIMEOUT = 2.5


# Per-model edit-format steering. Matching the edit tool format to how a model
# was trained reduces mistakes and wasted reasoning (OpenAI/Codex handle
# patch-style diffs best; Anthropic models — and most open-weight coding
# models, whose RL scaffolds use str_replace-style editors — do best with
# string-replacement). Our `patch` tool exposes both: mode="patch" (V4A
# multi-file) and mode="replace" (find-and-swap). We nudge each family toward
# its native format. Unknown families get nothing (the brief's neutral wording
# stands). Substrings match the model id; aligned with TOOL_USE_ENFORCEMENT_MODELS.
#
# GPT/Codex get V4A for ALL edits, single-file included: in codex-rs,
# apply_patch (V4A — apply_patch.lark) is the ONLY file editor, no
# str_replace-style tool exists, and the shipped model prompts say to use
# apply_patch even "for single file edits" — so a replace-mode nudge would
# steer those models toward a format their first-party harness never taught
# them.
_EDIT_FORMAT_GUIDANCE: dict[str, tuple[tuple[str, ...], str]] = {
    "patch": (
        ("gpt", "codex"),
        "- Edit format: author new files with `write_file`; for edits to "
        "existing code use `patch` with `mode='patch'` (V4A diff) — including "
        "single-file edits. It's the edit format you handle most reliably.",
    ),
    "replace": (
        ("claude", "sonnet", "opus", "haiku",
         "gemini", "gemma", "deepseek", "qwen", "kimi", "glm", "grok",
         "hermes", "llama", "mistral", "devstral", "minimax"),
        "- Edit format: author new files with `write_file`; for edits to "
        "existing code prefer `patch` in `mode='replace'` — match a unique "
        "snippet and swap it. Reach for `mode='patch'` (V4A) only when an edit "
        "genuinely spans several files at once.",
    ),
}


def _model_family(model: Optional[str]) -> Optional[str]:
    """Classify a model id into an edit-format family key, or ``None``.

    Used to steer the coding posture toward the edit tool format a model was
    trained on. Family-agnostic by design: an unrecognised model gets ``None``
    and the operating brief's neutral edit wording applies.
    """
    if not model:
        return None
    lowered = model.lower()
    for family, (needles, _line) in _EDIT_FORMAT_GUIDANCE.items():
        if any(n in lowered for n in needles):
            return family
    return None


def _edit_format_line(model: Optional[str]) -> str:
    """The edit-format guidance line for this model's family (``""`` if none)."""
    family = _model_family(model)
    if family is None:
        return ""
    return _EDIT_FORMAT_GUIDANCE[family][1]


# Operating brief for the coding posture. Tool names referenced here (read_file,
# search_files, patch, write_file, terminal, todo) are in the coding toolset and
# in _HERMES_CORE_TOOLS, so they're present on every surface this fires on.
CODING_AGENT_GUIDANCE = (
    "You are a coding agent pairing with the user inside their codebase. "
    "Operate like a careful senior engineer.\n"
    "\n"
    "Gather context first:\n"
    "- Read the relevant files with `read_file` and locate code with "
    "`search_files` before changing anything. Trace a symbol to its definition "
    "and usages rather than guessing its shape.\n"
    "- Batch independent lookups: when several reads/searches don't depend on "
    "each other, issue them together in one turn instead of one at a time.\n"
    "- Never invent files, symbols, APIs, or imports. If you haven't seen it in "
    "the repo, go look. Don't assume a library is available — check the project "
    "manifest (pyproject.toml / package.json / Cargo.toml / go.mod) and how "
    "neighbouring files import it.\n"
    "\n"
    "Make changes through the tools, not the chat:\n"
    "- Edit with `patch`/`write_file`. Do NOT print code blocks to the user as "
    "a substitute for editing — apply the change, then summarise it. Only show "
    "code when the user explicitly asks to see it.\n"
    "- Match the project's existing style and conventions; AGENTS.md / "
    "CLAUDE.md / .cursorrules already in context win over your defaults. Touch "
    "only what the task needs — no drive-by refactors, renames, or reformatting "
    "— and add any imports/dependencies your code requires.\n"
    "- If an edit fails to apply, re-read the file to get the current exact "
    "contents before retrying — don't repeat a stale patch. If the same region "
    "fails twice, rewrite the enclosing function or file with `write_file` "
    "instead of attempting a third patch.\n"
    "\n"
    "Verify, and know when to stop:\n"
    "- Use `terminal` for git, builds, tests, and inspection. Run the relevant "
    "tests/linter/build and confirm they pass before claiming the work is done.\n"
    "- Terminal state persists across calls: current directory and exported "
    "environment variables carry forward. Activate a virtualenv or export setup "
    "vars once, then reuse that state instead of re-sourcing it before every "
    "test command.\n"
    "- Fix root causes, not symptoms: when you find a bug, check sibling call "
    "paths for the same flaw and fix the class, not just the reported site.\n"
    "- When fixing linter/type errors on a file, stop after about three "
    "attempts on the same file and ask the user rather than looping.\n"
    "- Track multi-step work with `todo`. Reference code as `path:line` instead "
    "of pasting whole files.\n"
    "\n"
    "Respect the user's repo: don't commit, push, or rewrite history unless "
    "asked, and never read, print, or commit secrets — leave `.env` and "
    "credential files alone unless the user explicitly asks. The Workspace "
    "block below is a snapshot from session start — re-run `git status`/"
    "`git branch` before relying on it. Be concise: lead with the change or "
    "answer, not a preamble."
)


# ── Context profiles (declarative posture definitions) ──────────────────────


@dataclass(frozen=True)
class ContextProfile:
    """A named operating posture. Pure data — consumers read these fields.

    ``toolset``      — collapse to this toolset (+ enabled MCP) when no explicit
                       selection is pinned; ``None`` keeps the platform default.
    ``guidance``     — operating brief injected into the stable system prompt;
                       ``""`` injects nothing.
    ``model_hint``   — routing preference key for smart model routing
                       (extension seam; not yet consumed by the router).
    ``memory_policy``— memory namespace/weighting hint (extension seam).
    ``compact_skill_categories`` — skill categories DEMOTED to names-only in
                       the system-prompt skill index under the opt-in ``focus``
                       mode. Never hidden: every skill name stays visible
                       (so memory-anchored recall keeps working) — only the
                       descriptions are dropped to cut index noise. Deny-list
                       semantics so unknown/custom categories keep full
                       entries.
    """

    name: str
    toolset: Optional[str] = None
    guidance: str = ""
    model_hint: Optional[str] = None
    memory_policy: str = "default"
    compact_skill_categories: tuple[str, ...] = ()


# Skill categories that are clearly not part of a coding workflow. Demoted to
# names-only in the prompt's skill index under the opt-in ``focus`` mode only
# (deny-list — anything not listed here, incl. custom user categories, keeps
# full entries). Coding-adjacent categories (devops, github, mcp,
# data-science, diagramming, research, security, …) are intentionally absent.
_NON_CODING_SKILL_CATEGORIES = (
    "apple", "communication", "cooking", "creative", "email", "finance",
    "gaming", "gifs", "health", "media", "music", "note-taking",
    "productivity", "shopping", "smart-home", "social-media", "travel",
    "yuanbao",
)


GENERAL_PROFILE = ContextProfile(name="general")
CODING_PROFILE = ContextProfile(
    name="coding",
    toolset=CODING_TOOLSET,
    guidance=CODING_AGENT_GUIDANCE,
    model_hint="coding",
    memory_policy="project",
    compact_skill_categories=_NON_CODING_SKILL_CATEGORIES,
)

_PROFILES: dict[str, ContextProfile] = {
    GENERAL_PROFILE.name: GENERAL_PROFILE,
    CODING_PROFILE.name: CODING_PROFILE,
}


def get_profile(name: str) -> ContextProfile:
    """Return a registered profile, falling back to ``general``."""
    return _PROFILES.get(name, GENERAL_PROFILE)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _coding_mode(config: Optional[dict[str, Any]]) -> str:
    """Return the normalized ``agent.coding_context`` mode (auto/focus/on/off)."""
    if config is None:
        try:
            from hermes_cli.config import load_config

            config = load_config()
        except Exception:
            config = {}
    raw = ((config or {}).get("agent", {}) or {}).get("coding_context", "auto")
    mode = str(raw).strip().lower()
    if mode in {"focus", "strict", "lean"}:
        return "focus"
    if mode in {"on", "true", "yes", "1", "always"}:
        return "on"
    if mode in {"off", "false", "no", "0", "never"}:
        return "off"
    return "auto"


def _coding_instructions(config: Optional[dict[str, Any]]) -> str:
    """Standing operator instructions for the coding posture (config).

    ``agent.coding_instructions`` — a string or list of strings appended to the
    coding brief as an extra stable system block, so a user can pin project-wide
    coding-workflow rules (e.g. "for UI work don't run tsc/lint until I approve;
    clean the diff before committing") without editing the shipped brief.
    Cache-safe: resolved once per session into the stable system-prompt tier,
    like the rest of the posture.
    """
    if config is None:
        try:
            from hermes_cli.config import load_config

            config = load_config()
        except Exception:
            config = {}
    raw = ((config or {}).get("agent", {}) or {}).get("coding_instructions", "")
    if isinstance(raw, (list, tuple)):
        return "\n".join(str(item).strip() for item in raw if str(item).strip())
    return str(raw or "").strip()


def _resolve_cwd(cwd: Optional[str | Path]) -> Path:
    if cwd:
        return Path(cwd).expanduser()
    try:
        from agent.runtime_cwd import resolve_agent_cwd

        return resolve_agent_cwd()
    except Exception:
        return Path(os.getcwd())


def _git_root(cwd: Path) -> Optional[Path]:
    current = cwd.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _home() -> Optional[Path]:
    try:
        return Path.home().resolve()
    except (OSError, RuntimeError):
        return None


def _marker_root(cwd: Path) -> Optional[Path]:
    """Nearest ancestor that looks like a project root, or ``None``.

    Walks up at most a few levels so a manifest in the workspace root counts
    even when the user is in a subdirectory. ``$HOME`` itself is skipped — a
    Makefile or AGENTS.md sitting in the home directory is global user config,
    not a project-root signal.
    """
    current = cwd.resolve()
    home = _home()
    # Shared world-writable temp roots are never project roots: a stray
    # manifest in /tmp (left by any process) must not flip every session
    # whose cwd lives under the temp dir into the coding posture. Same
    # reasoning as the $HOME skip below.
    try:
        temp_root = Path(tempfile.gettempdir()).resolve()
    except Exception:
        temp_root = None
    for depth, parent in enumerate([current, *current.parents]):
        if depth > 6:
            break
        if parent == home or (temp_root is not None and parent == temp_root):
            continue
        for marker in _PROJECT_MARKERS:
            if (parent / marker).exists():
                return parent
    return None


def _detect_profile_name(mode: str, platform: str, cwd_str: str) -> str:
    """Resolve which profile applies.

    ``auto``/``focus``: coding when the surface is interactive AND the cwd is a
    code workspace (a git repo or a recognised project root). ``on``: always
    coding. ``off``: always general.

    A git repo rooted at ``$HOME`` (the dotfiles pattern) is NOT a workspace
    signal — without the guard, every session anywhere under a dotfiles-managed
    home directory would silently flip to the coding posture.

    Detection is intentionally not memoized: it's a handful of ``stat`` calls,
    and callers resolve the mode once per session anyway. Caching here would
    risk a stale posture if a long-lived process (gateway/TUI) serves sessions
    from different working directories.
    """
    if mode == "off":
        return GENERAL_PROFILE.name
    if mode == "on":
        return CODING_PROFILE.name
    if platform and platform.strip().lower() not in INTERACTIVE_CODING_PLATFORMS:
        return GENERAL_PROFILE.name
    cwd = Path(cwd_str)
    # A recognized project root (manifest / AGENTS.md / .cursorrules) is a code
    # workspace on its own — cheap stat checks, no scan.
    if _marker_root(cwd) is not None:
        return CODING_PROFILE.name
    git_root = _git_root(cwd)
    if git_root is not None and git_root == _home():
        git_root = None  # dotfiles repo at $HOME — not a code workspace
    # A bare git repo only counts when it actually holds code, so `git init` on a
    # notes/writing/research folder stays in the general posture.
    if git_root is not None and _has_code_files(git_root):
        return CODING_PROFILE.name
    return GENERAL_PROFILE.name


# ── RuntimeMode (the seam) ──────────────────────────────────────────────────


@dataclass(frozen=True)
class RuntimeMode:
    """The resolved operating posture for a session. Immutable by construction.

    Built once via :func:`resolve_runtime_mode` and consumed by every domain
    that cares about the coding/general distinction. Never mutate or re-resolve
    mid-session — that would break the prompt cache.
    """

    profile: ContextProfile
    surface: str
    cwd: Path
    # The normalized ``agent.coding_context`` mode this posture was resolved
    # under (auto/focus/on/off). Toolset collapse is gated on ``focus``.
    config_mode: str = "auto"
    # The model id this session runs (e.g. "anthropic/claude-opus-4.8"). Used
    # only to steer edit-format guidance toward the model's family — see
    # ``_edit_format_line``. Fixed for the session, so cache-safe.
    model: Optional[str] = None
    # Standing operator instructions (``agent.coding_instructions``), appended
    # as an extra stable system block. Empty unless the user configures it.
    instructions: str = ""

    @property
    def kind(self) -> str:
        return self.profile.name

    @property
    def is_coding(self) -> bool:
        return self.profile.name == CODING_PROFILE.name

    def toolset_selection(self, config: Optional[dict[str, Any]] = None) -> Optional[list[str]]:
        """Toolset list for this posture, or ``None`` to keep the platform default.

        Non-``None`` only under the opt-in ``focus`` mode. The default posture
        is prompt-only: most strippable toolsets are off-by-default anyway, and
        a user who explicitly enabled one (image-gen for frontend/game assets,
        messaging for build notifications, …) keeps it while coding.

        Callers apply this only when the user hasn't pinned an explicit
        selection (``--toolsets``, ``HERMES_TUI_TOOLSETS``, …); they never
        override a pin. Returns the profile's toolset plus enabled MCP servers.
        """
        if self.config_mode != "focus":
            return None
        if self.profile.toolset is None:
            return None
        return [self.profile.toolset, *_enabled_mcp_servers(config)]

    def system_blocks(self) -> list[str]:
        """Stable system-prompt blocks for this posture (brief + workspace).

        The operating brief carries a model-family edit-format nudge appended
        to it (one cached string, not a separate block) so the model is steered
        toward the `patch` mode it handles best — see ``_edit_format_line``.
        """
        if not self.is_coding:
            return []
        blocks: list[str] = []
        if self.profile.guidance:
            brief = self.profile.guidance
            edit_line = _edit_format_line(self.model)
            if edit_line:
                brief = f"{brief}\n{edit_line}"
            blocks.append(brief)
        workspace = build_coding_workspace_block(self.cwd)
        if workspace:
            blocks.append(workspace)
        # Operator instructions ride their own block so the brief (block 0) stays
        # byte-stable and cache-keyed independently of user config.
        if self.instructions:
            blocks.append(f"Operator instructions (from config):\n{self.instructions}")
        return blocks

    def compact_skill_categories(self) -> frozenset[str]:
        """Skill categories to demote to names-only in the prompt's skill index.

        Gated on the opt-in ``focus`` mode, like the toolset collapse: the
        default posture leaves the skill index untouched. Users who didn't ask
        for a lean prompt keep full entries for every category — index changes
        under ``auto`` proved too surprising in practice, even names-only ones
        (a demoted description is information the model no longer weighs when
        deciding what to load).

        Demoted — never hidden — even under ``focus``. An earlier revision
        fully pruned these categories from the index, which caused silent
        capability loss in a real workflow: agent-created skills are the
        model's accumulated project memory (server-ops runbooks, learned
        pitfalls, …), and models do not reliably reach for ``skills_list`` to
        rediscover what the index stopped showing them. Names-only keeps every
        skill loadable on recall while still cutting the description noise.
        """
        if not self.is_coding or self.config_mode != "focus":
            return frozenset()
        return frozenset(self.profile.compact_skill_categories)


def resolve_runtime_mode(
    *,
    platform: Optional[str] = None,
    cwd: Optional[str | Path] = None,
    config: Optional[dict[str, Any]] = None,
    model: Optional[str] = None,
) -> RuntimeMode:
    """Resolve the operating posture once. Cheap — a handful of ``stat`` calls.

    This is the single entry point every domain should call. The returned
    object is immutable and safe to cache for the session. Detection itself is
    intentionally *not* memoized (see ``_detect_profile_name``) so a long-lived
    process can't pin a stale posture; callers resolve once per session and
    hold the result. ``model`` is recorded only to steer edit-format guidance;
    it never affects detection.
    """
    resolved_cwd = _resolve_cwd(cwd)
    mode = _coding_mode(config)
    name = _detect_profile_name(
        mode, (platform or "").strip().lower(), str(resolved_cwd)
    )
    return RuntimeMode(
        profile=get_profile(name),
        surface=platform or "",
        cwd=resolved_cwd,
        config_mode=mode,
        model=model,
        instructions=_coding_instructions(config),
    )


# ── Back-compat surface (thin wrappers over RuntimeMode) ────────────────────


def is_coding_context(
    *,
    platform: Optional[str] = None,
    cwd: Optional[str | Path] = None,
    config: Optional[dict[str, Any]] = None,
) -> bool:
    """Whether Hermes should operate in its coding posture right now."""
    return resolve_runtime_mode(platform=platform, cwd=cwd, config=config).is_coding


def coding_selection(
    *,
    platform: Optional[str] = None,
    cwd: Optional[str | Path] = None,
    config: Optional[dict[str, Any]] = None,
) -> Optional[list[str]]:
    """Toolset selection for the coding posture.

    ``None`` unless the user opted into ``focus`` mode AND the posture is
    active — the default coding posture never overrides configured toolsets.
    """
    return resolve_runtime_mode(
        platform=platform, cwd=cwd, config=config
    ).toolset_selection(config)


def coding_system_blocks(
    *,
    platform: Optional[str] = None,
    cwd: Optional[str | Path] = None,
    config: Optional[dict[str, Any]] = None,
    model: Optional[str] = None,
) -> list[str]:
    """Stable system-prompt blocks for the current posture (empty when general).

    ``model`` steers the brief's edit-format nudge toward the model's family.
    """
    return resolve_runtime_mode(
        platform=platform, cwd=cwd, config=config, model=model
    ).system_blocks()


def coding_compact_skill_categories(
    *,
    platform: Optional[str] = None,
    cwd: Optional[str | Path] = None,
    config: Optional[dict[str, Any]] = None,
) -> frozenset[str]:
    """Skill categories the active posture demotes to names-only in the index.

    Empty outside the coding posture and outside the opt-in ``focus`` mode —
    the default posture never touches the skill index. Under ``focus``,
    demoted — never hidden: every skill name stays in the index and remains
    loadable via ``skill_view`` / ``skills_list``; only descriptions are
    dropped.
    """
    return resolve_runtime_mode(
        platform=platform, cwd=cwd, config=config
    ).compact_skill_categories()


def _enabled_mcp_servers(config: Optional[dict[str, Any]]) -> list[str]:
    """Names of MCP servers the user has enabled — kept in the coding posture.

    MCP servers (figma, browser, tophat, …) are explicitly configured and part
    of the coding workflow, not noise to strip.
    """
    try:
        from hermes_cli.config import read_raw_config
        from hermes_cli.tools_config import _parse_enabled_flag

        servers = read_raw_config().get("mcp_servers") or {}
        return [
            str(name)
            for name, cfg in servers.items()
            if isinstance(cfg, dict)
            and _parse_enabled_flag(cfg.get("enabled", True), default=True)
        ]
    except Exception:
        return []


# ── git/workspace probe ─────────────────────────────────────────────────────


def _git(cwd: Path, *args: str) -> str:
    """``git -C <cwd> <args>`` → stripped stdout, or ``""`` on any failure.

    Uses the shared :func:`bounded_git_probe` so the post-kill cleanup is bounded
    on Windows — a plain ``subprocess.run(timeout=...)`` here deadlocked the agent
    turn inside ``build_coding_workspace_block`` when a killed git left a suspended
    descendant holding the pipe handles (issue #66037).
    """
    return bounded_git_probe(["git", "-C", str(cwd), *args], timeout=_GIT_TIMEOUT)


def _parse_status(porcelain: str) -> tuple[dict[str, str], dict[str, int]]:
    """Parse ``git status --porcelain=2 --branch`` into branch + counts."""
    branch: dict[str, str] = {}
    counts = {"staged": 0, "modified": 0, "untracked": 0, "conflicts": 0}
    for line in porcelain.splitlines():
        if line.startswith("# branch.head"):
            branch["head"] = line.split(maxsplit=2)[-1]
        elif line.startswith("# branch.upstream"):
            branch["upstream"] = line.split(maxsplit=2)[-1]
        elif line.startswith("# branch.ab"):
            parts = line.split()
            branch["ahead"], branch["behind"] = parts[2].lstrip("+"), parts[3].lstrip("-")
        elif line.startswith(("1 ", "2 ")):
            xy = line.split(maxsplit=2)[1]
            if xy[0] != ".":
                counts["staged"] += 1
            if xy[1] != ".":
                counts["modified"] += 1
        elif line.startswith("u "):
            counts["conflicts"] += 1
        elif line.startswith("? "):
            counts["untracked"] += 1
    return branch, counts


def _read_small(path: Path) -> str:
    """Read a small text file, or ``""`` — never raises, never reads huge files."""
    try:
        if not path.is_file() or path.stat().st_size > _MAX_FACT_FILE_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


@dataclass(frozen=True)
class ProjectFacts:
    """Structured project facts — the model's verify loop, detected once.

    The same data that feeds the workspace snapshot, exposed structurally so
    non-prompt consumers (e.g. the desktop verify UI) read it instead of
    re-detecting and drifting from the prompt.
    """

    manifests: list[str]
    package_managers: list[str]
    verify_commands: list[str]
    context_files: list[str]


def detect_project_facts(root: Path) -> ProjectFacts:
    """Detect manifests, package manager(s), verify commands, and context files.

    Cheap: stat calls plus reads of a couple of small files. The single source
    of truth for both the prompt snapshot (:func:`_project_facts`) and the
    gateway's ``project.facts`` — so the UI never re-sniffs verify commands.
    """
    manifests = [m for m in _PROJECT_MARKERS if m not in _CONTEXT_FILES and (root / m).is_file()]
    package_managers = list(
        dict.fromkeys(pm for lock, pm in (*_PY_LOCKFILES, *_JS_LOCKFILES) if (root / lock).is_file())
    )

    verify: list[str] = []
    if (root / "scripts" / "run_tests.sh").is_file():
        verify.append("scripts/run_tests.sh")
    if (root / "package.json").is_file():
        try:
            scripts = json.loads(_read_small(root / "package.json") or "{}").get("scripts") or {}
        except (json.JSONDecodeError, AttributeError):
            scripts = {}
        js_pm = next((pm for lock, pm in _JS_LOCKFILES if (root / lock).is_file()), "npm")
        verify.extend(f"{js_pm} run {name}" for name in _VERIFY_TARGETS if name in scripts)
    if (root / "pytest.ini").is_file() or "[tool.pytest" in _read_small(root / "pyproject.toml"):
        verify.append("pytest")
    makefile = _read_small(root / "Makefile")
    if makefile:
        verify.extend(
            f"make {name}" for name in _VERIFY_TARGETS
            if re.search(rf"^{re.escape(name)}\s*:", makefile, re.MULTILINE)
        )

    return ProjectFacts(
        manifests=manifests,
        package_managers=package_managers,
        verify_commands=list(dict.fromkeys(verify))[:_MAX_VERIFY_COMMANDS],
        context_files=[c for c in _CONTEXT_FILES if (root / c).is_file()],
    )


def _project_facts(root: Path) -> list[str]:
    """Render :func:`detect_project_facts` as workspace-snapshot lines.

    Hands the model its *verify loop* up front — which manifest, which package
    manager, and the exact test/lint/build commands — instead of making it
    rediscover them every session. Built once at prompt-build time; the string
    output must stay byte-stable to preserve the prompt cache.
    """
    f = detect_project_facts(root)
    facts: list[str] = []

    if f.manifests:
        line = f"- Project: {', '.join(f.manifests[:6])}"
        if f.package_managers:
            line += f" ({'/'.join(f.package_managers)})"
        facts.append(line)
    if f.verify_commands:
        facts.append(f"- Verify: {'; '.join(f.verify_commands)}")
    if f.context_files:
        facts.append(f"- Context files: {', '.join(f.context_files)}")

    return facts


def project_facts_for(cwd: Optional[str | Path] = None) -> Optional[dict[str, Any]]:
    """Structured project facts for ``cwd`` — ``None`` outside a workspace.

    Same detection the system-prompt snapshot uses (git root, else marker root),
    exposed for non-prompt consumers (the desktop verify UI) so they never
    re-derive "are we coding?" or duplicate the verify-command sniffing.
    """
    resolved = _resolve_cwd(cwd)
    root = _git_root(resolved) or _marker_root(resolved)
    if root is None:
        return None

    f = detect_project_facts(root)
    return {
        "root": str(root),
        "manifests": f.manifests,
        "packageManagers": f.package_managers,
        "verifyCommands": f.verify_commands,
        "contextFiles": f.context_files,
    }


def build_coding_workspace_block(cwd: Optional[str | Path] = None) -> str:
    """Workspace snapshot for the system prompt (empty outside a workspace).

    Git state (branch/status/commits) when the cwd is in a repo, plus detected
    project facts (manifest, package manager, verify commands, context files)
    — so marker-only (non-git) projects still get a snapshot.
    """
    resolved = _resolve_cwd(cwd)
    git_root = _git_root(resolved)
    root = git_root or _marker_root(resolved)
    if root is None:
        return ""

    lines = ["Workspace (snapshot at session start — re-check with `git` before acting on it):"]
    lines.append(f"- Root: {root}")

    if git_root is not None:
        branch, counts = _parse_status(_git(root, "status", "--porcelain=2", "--branch"))
        head = branch.get("head", "")
        if head and head != "(detached)":
            line = f"- Branch: {head}"
            if branch.get("upstream"):
                line += f" \u2192 {branch['upstream']}"
                ahead, behind = branch.get("ahead", "0"), branch.get("behind", "0")
                if ahead != "0" or behind != "0":
                    line += f" (ahead {ahead}, behind {behind})"
            lines.append(line)
        elif head == "(detached)":
            lines.append("- Branch: (detached HEAD)")

        # Linked worktree: the per-worktree git dir differs from the shared common dir.
        # We surface the fact that it's a worktree (so the model knows branches/stashes
        # are shared state) but deliberately do NOT expose the primary tree path —
        # giving the model a second absolute path causes it to sometimes run commands
        # in the wrong directory.
        git_dir, common_dir = _git(root, "rev-parse", "--git-dir"), _git(root, "rev-parse", "--git-common-dir")
        if git_dir and common_dir and Path(git_dir).resolve() != Path(common_dir).resolve():
            lines.append("- Worktree: linked (git state shared with primary tree)")

        dirty = [f"{n} {label}" for label, n in (
            ("staged", counts["staged"]), ("modified", counts["modified"]),
            ("untracked", counts["untracked"]), ("conflicts", counts["conflicts"]),
        ) if n]
        lines.append(f"- Status: {', '.join(dirty) if dirty else 'clean'}")

        recent = _git(root, "log", "-3", "--pretty=%h %s")
        if recent:
            lines.append("- Recent commits:")
            lines.extend(f"    {c}" for c in recent.splitlines())

    lines.extend(_project_facts(root))
    return "\n".join(lines)
