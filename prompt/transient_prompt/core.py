"""一次性提示词插件的通用编排框架。

瞬态插件不使用缓存。每次调用 ``consume`` 都表示宿主准备构建一个新的
模型请求；插件应在返回提示词后同步清除自己的来源，使内容最多被加载一次。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable


class TransientPromptPluginError(RuntimeError):
    """一次性提示词插件执行失败。"""


class DuplicateTransientPluginError(TransientPromptPluginError):
    """注册了重名的一次性提示词插件。"""


@dataclass(frozen=True, slots=True)
class TransientPromptContext:
    """传递给一次性提示词插件的只读上下文。"""

    values: Mapping[str, Any] = field(default_factory=dict)

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
            raise TransientPromptPluginError(
                f"缺少必需的一次性提示词上下文：{key}"
            ) from exc


TransientPromptOutput = str | Sequence[str] | None


@runtime_checkable
class TransientPromptPlugin(Protocol):
    """独立的一次性提示词插件协议。"""

    name: str
    priority: int

    def enabled(self, context: TransientPromptContext) -> bool:
        """返回插件在本次请求中是否启用。"""

    def consume(self, context: TransientPromptContext) -> TransientPromptOutput:
        """返回并消费本次请求的提示词。"""


@dataclass(frozen=True, slots=True)
class TransientPromptFragment:
    """单个插件消费后产生的提示词片段。"""

    plugin: str
    priority: int
    content: str


class TransientPromptRegistry:
    """维护相互独立的一次性提示词插件。"""

    def __init__(self) -> None:
        self._plugins: dict[str, tuple[int, TransientPromptPlugin]] = {}
        self._next_order = 0

    def register(self, plugin: TransientPromptPlugin) -> None:
        if not isinstance(plugin, TransientPromptPlugin):
            raise TypeError("插件必须实现 TransientPromptPlugin 协议")
        if not isinstance(plugin.name, str) or not plugin.name.strip():
            raise ValueError("插件 name 必须是非空字符串")
        if not isinstance(plugin.priority, int):
            raise ValueError("插件 priority 必须是整数")
        if plugin.name in self._plugins:
            raise DuplicateTransientPluginError(
                f"一次性提示词插件已存在：{plugin.name}"
            )
        self._plugins[plugin.name] = (self._next_order, plugin)
        self._next_order += 1

    def unregister(self, name: str) -> bool:
        return self._plugins.pop(name, None) is not None

    def snapshot(self) -> tuple[TransientPromptPlugin, ...]:
        entries = sorted(
            self._plugins.values(),
            key=lambda entry: (entry[1].priority, entry[0]),
        )
        return tuple(plugin for _, plugin in entries)


class TransientPromptBuilder:
    """按优先级消费插件，并组装当前请求的一次性提示词。"""

    def __init__(
        self,
        registry: TransientPromptRegistry | None = None,
        *,
        separator: str = "\n\n",
    ) -> None:
        if not separator:
            raise ValueError("separator 不能为空")
        self.registry = registry or TransientPromptRegistry()
        self.separator = separator

    def consume(
        self,
        context: TransientPromptContext | Mapping[str, Any] | None = None,
    ) -> str:
        return self.separator.join(
            fragment.content for fragment in self.consume_fragments(context)
        )

    def consume_fragments(
        self,
        context: TransientPromptContext | Mapping[str, Any] | None = None,
    ) -> tuple[TransientPromptFragment, ...]:
        prompt_context = (
            context
            if isinstance(context, TransientPromptContext)
            else TransientPromptContext(context or {})
        )
        fragments: list[TransientPromptFragment] = []
        for plugin in self.registry.snapshot():
            try:
                if not plugin.enabled(prompt_context):
                    continue
                for content in self._normalize(plugin.consume(prompt_context)):
                    fragments.append(
                        TransientPromptFragment(
                            plugin=plugin.name,
                            priority=plugin.priority,
                            content=content,
                        )
                    )
            except Exception as exc:
                raise TransientPromptPluginError(
                    f"一次性提示词插件 {plugin.name!r} 执行失败"
                ) from exc
        return tuple(fragments)

    @staticmethod
    def _normalize(output: TransientPromptOutput) -> tuple[str, ...]:
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


__all__ = [
    "DuplicateTransientPluginError",
    "TransientPromptBuilder",
    "TransientPromptContext",
    "TransientPromptFragment",
    "TransientPromptOutput",
    "TransientPromptPlugin",
    "TransientPromptPluginError",
    "TransientPromptRegistry",
]
