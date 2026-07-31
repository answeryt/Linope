"""通用、可缓存且相互隔离的系统提示词插件框架。

核心模块只负责编排，不包含任何产品特定提示词。插件只能读取
``PromptContext`` 并返回文本，不能通过框架查询、导入或调用其他插件。
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable


class PromptTier(str, Enum):
    """系统提示词的固定拼接层级。"""

    STABLE = "stable"
    CONTEXT = "context"
    VOLATILE = "volatile"


_TIER_ORDER = {
    PromptTier.STABLE: 0,
    PromptTier.CONTEXT: 1,
    PromptTier.VOLATILE: 2,
}


class PromptPluginError(RuntimeError):
    """系统提示词插件错误。"""


class DuplicatePluginError(PromptPluginError):
    """注册了重名插件。"""


class PluginIsolationError(PromptPluginError):
    """插件声明了框架禁止的插件间依赖。"""


@dataclass(frozen=True, slots=True)
class PromptContext:
    """所有插件共享的只读输入。

    ``values`` 会被浅拷贝并包装为只读映射，避免插件之间通过修改共享
    字典传递状态。``cache_key`` 由宿主按会话提供；为 ``None`` 时不缓存。
    """

    values: Mapping[str, Any] = field(default_factory=dict)
    cache_key: Hashable | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "values",
            MappingProxyType(dict(self.values)),
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def require(self, key: str) -> Any:
        try:
            return self.values[key]
        except KeyError as exc:
            raise PromptPluginError(f"缺少必需的提示词上下文：{key}") from exc


PromptOutput = str | Sequence[str] | None


@runtime_checkable
class SystemPromptPlugin(Protocol):
    """独立提示词插件协议。

    插件应只依赖本协议及自身业务依赖。框架不会向插件暴露注册表、
    builder 或其他插件实例，因此插件之间无法通过框架相互调用。
    """

    name: str
    tier: PromptTier
    priority: int

    def enabled(self, context: PromptContext) -> bool:
        """返回当前上下文是否启用插件。"""

    def render(self, context: PromptContext) -> PromptOutput:
        """渲染一个或多个提示词片段。"""


@dataclass(frozen=True, slots=True)
class FunctionPromptPlugin:
    """将独立函数适配为提示词插件。"""

    name: str
    render_fn: Callable[[PromptContext], PromptOutput]
    tier: PromptTier = PromptTier.STABLE
    priority: int = 100
    enabled_fn: Callable[[PromptContext], bool] | None = None

    def enabled(self, context: PromptContext) -> bool:
        return self.enabled_fn(context) if self.enabled_fn is not None else True

    def render(self, context: PromptContext) -> PromptOutput:
        return self.render_fn(context)


@dataclass(frozen=True, slots=True)
class PromptFragment:
    """完成规范化后的单个提示词片段。"""

    plugin: str
    tier: PromptTier
    priority: int
    content: str


@dataclass(frozen=True, slots=True)
class PromptParts:
    """按缓存友好顺序排列的三层提示词。"""

    stable: str = ""
    context: str = ""
    volatile: str = ""

    def join(self, separator: str = "\n\n") -> str:
        return separator.join(
            part
            for part in (self.stable, self.context, self.volatile)
            if part
        )

    def as_dict(self) -> dict[str, str]:
        return {
            PromptTier.STABLE.value: self.stable,
            PromptTier.CONTEXT.value: self.context,
            PromptTier.VOLATILE.value: self.volatile,
        }


@dataclass(frozen=True, slots=True)
class PluginFailure:
    """在容错模式下记录的插件失败。"""

    plugin: str
    error: Exception


@dataclass(frozen=True, slots=True)
class PromptBuildResult:
    """系统提示词构建结果及可选诊断信息。"""

    parts: PromptParts
    fragments: tuple[PromptFragment, ...]
    failures: tuple[PluginFailure, ...] = ()

    @property
    def prompt(self) -> str:
        return self.parts.join()


@dataclass(frozen=True, slots=True)
class _RegisteredPlugin:
    plugin: SystemPromptPlugin
    order: int


class SystemPromptRegistry:
    """维护独立插件集合，不提供插件间查找能力。"""

    def __init__(self) -> None:
        self._plugins: dict[str, _RegisteredPlugin] = {}
        self._next_order = 0
        self._revision = 0

    @property
    def revision(self) -> int:
        return self._revision

    def register(self, plugin: SystemPromptPlugin) -> None:
        self._validate(plugin)
        if plugin.name in self._plugins:
            raise DuplicatePluginError(f"系统提示词插件已存在：{plugin.name}")
        self._plugins[plugin.name] = _RegisteredPlugin(
            plugin=plugin,
            order=self._next_order,
        )
        self._next_order += 1
        self._revision += 1

    def unregister(self, name: str) -> bool:
        removed = self._plugins.pop(name, None)
        if removed is not None:
            self._revision += 1
            return True
        return False

    def clear(self) -> None:
        if self._plugins:
            self._plugins.clear()
            self._revision += 1

    def snapshot(self) -> tuple[SystemPromptPlugin, ...]:
        """返回稳定排序后的插件快照，不暴露给插件本身。"""

        entries = sorted(
            self._plugins.values(),
            key=lambda entry: (
                _TIER_ORDER[entry.plugin.tier],
                entry.plugin.priority,
                entry.order,
            ),
        )
        return tuple(entry.plugin for entry in entries)

    @staticmethod
    def _validate(plugin: SystemPromptPlugin) -> None:
        if not isinstance(plugin, SystemPromptPlugin):
            raise TypeError("插件必须实现 SystemPromptPlugin 协议")
        if not isinstance(plugin.name, str) or not plugin.name.strip():
            raise ValueError("插件 name 必须是非空字符串")
        if not isinstance(plugin.tier, PromptTier):
            raise ValueError("插件 tier 必须是 PromptTier")
        if not isinstance(plugin.priority, int):
            raise ValueError("插件 priority 必须是整数")

        # 显式拒绝常见的插件依赖声明。插件组合只能由宿主通过注册顺序
        # 和共享上下文完成，不能形成插件依赖图。
        for attribute in ("depends_on", "dependencies", "requires_plugins"):
            dependency = getattr(plugin, attribute, None)
            if dependency:
                raise PluginIsolationError(
                    f"插件 {plugin.name!r} 声明了禁止的插件间依赖：{attribute}"
                )


class SystemPromptBuilder:
    """调用隔离插件并组装系统提示词。"""

    def __init__(
        self,
        registry: SystemPromptRegistry | None = None,
        *,
        separator: str = "\n\n",
        fail_fast: bool = True,
        max_cache_entries: int = 128,
    ) -> None:
        if not separator:
            raise ValueError("separator 不能为空")
        if max_cache_entries < 0:
            raise ValueError("max_cache_entries 不能为负数")
        self.registry = registry or SystemPromptRegistry()
        self.separator = separator
        self.fail_fast = fail_fast
        self.max_cache_entries = max_cache_entries
        self._cache: OrderedDict[
            tuple[int, Hashable], PromptBuildResult
        ] = OrderedDict()

    def build(
        self,
        context: PromptContext | Mapping[str, Any] | None = None,
        *,
        cache_key: Hashable | None = None,
        use_cache: bool = True,
    ) -> str:
        return self.build_result(
            context,
            cache_key=cache_key,
            use_cache=use_cache,
        ).parts.join(self.separator)

    def build_parts(
        self,
        context: PromptContext | Mapping[str, Any] | None = None,
        *,
        cache_key: Hashable | None = None,
        use_cache: bool = True,
    ) -> PromptParts:
        return self.build_result(
            context,
            cache_key=cache_key,
            use_cache=use_cache,
        ).parts

    def build_result(
        self,
        context: PromptContext | Mapping[str, Any] | None = None,
        *,
        cache_key: Hashable | None = None,
        use_cache: bool = True,
    ) -> PromptBuildResult:
        prompt_context = self._coerce_context(context, cache_key)
        effective_key = prompt_context.cache_key
        internal_key = (
            (self.registry.revision, effective_key)
            if use_cache and effective_key is not None and self.max_cache_entries
            else None
        )

        if internal_key is not None:
            cached = self._cache.get(internal_key)
            if cached is not None:
                self._cache.move_to_end(internal_key)
                return cached

        fragments: list[PromptFragment] = []
        failures: list[PluginFailure] = []
        for plugin in self.registry.snapshot():
            try:
                if not plugin.enabled(prompt_context):
                    continue
                for content in self._normalize_output(plugin.render(prompt_context)):
                    fragments.append(
                        PromptFragment(
                            plugin=plugin.name,
                            tier=plugin.tier,
                            priority=plugin.priority,
                            content=content,
                        )
                    )
            except Exception as exc:
                if self.fail_fast:
                    raise PromptPluginError(
                        f"系统提示词插件 {plugin.name!r} 执行失败"
                    ) from exc
                failures.append(PluginFailure(plugin=plugin.name, error=exc))

        parts = self._build_parts(fragments)
        result = PromptBuildResult(
            parts=parts,
            fragments=tuple(fragments),
            failures=tuple(failures),
        )
        if internal_key is not None:
            self._cache[internal_key] = result
            self._cache.move_to_end(internal_key)
            while len(self._cache) > self.max_cache_entries:
                self._cache.popitem(last=False)
        return result

    def invalidate(self, cache_key: Hashable | None = None) -> None:
        """清除全部缓存，或清除指定宿主会话的缓存。"""

        if cache_key is None:
            self._cache.clear()
            return
        for key in tuple(self._cache):
            if key[1] == cache_key:
                self._cache.pop(key, None)

    @staticmethod
    def _coerce_context(
        context: PromptContext | Mapping[str, Any] | None,
        cache_key: Hashable | None,
    ) -> PromptContext:
        if isinstance(context, PromptContext):
            if cache_key is not None and cache_key != context.cache_key:
                raise ValueError("cache_key 与 PromptContext.cache_key 冲突")
            return context
        return PromptContext(values=context or {}, cache_key=cache_key)

    @staticmethod
    def _normalize_output(output: PromptOutput) -> tuple[str, ...]:
        if output is None:
            return ()
        candidates: Sequence[str] = (output,) if isinstance(output, str) else output
        normalized: list[str] = []
        for candidate in candidates:
            if not isinstance(candidate, str):
                raise TypeError("插件输出必须是字符串、字符串序列或 None")
            content = candidate.strip()
            if content:
                normalized.append(content)
        return tuple(normalized)

    def _build_parts(self, fragments: list[PromptFragment]) -> PromptParts:
        by_tier: dict[PromptTier, list[str]] = {
            PromptTier.STABLE: [],
            PromptTier.CONTEXT: [],
            PromptTier.VOLATILE: [],
        }
        for fragment in fragments:
            by_tier[fragment.tier].append(fragment.content)
        return PromptParts(
            stable=self.separator.join(by_tier[PromptTier.STABLE]),
            context=self.separator.join(by_tier[PromptTier.CONTEXT]),
            volatile=self.separator.join(by_tier[PromptTier.VOLATILE]),
        )


__all__ = [
    "DuplicatePluginError",
    "FunctionPromptPlugin",
    "PluginFailure",
    "PluginIsolationError",
    "PromptBuildResult",
    "PromptContext",
    "PromptFragment",
    "PromptOutput",
    "PromptParts",
    "PromptPluginError",
    "PromptTier",
    "SystemPromptBuilder",
    "SystemPromptPlugin",
    "SystemPromptRegistry",
]
