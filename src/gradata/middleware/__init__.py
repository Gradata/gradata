"""Runtime middleware adapters for non-Claude-Code agents (OpenAI, Anthropic,
LangChain, CrewAI): inject learned rules into prompts and enforce RULE-tier
patterns on outputs. GRADATA_BYPASS=1 = kill switch. Optional deps raise
with install hint if missing.
"""

from __future__ import annotations

from ._core import (
    RuleSource,
    RuleViolation,
    build_brain_rules_block,
    check_output,
    is_bypassed,
)

# Adapters are exposed via lazy __getattr__ so importing the package
# doesn't require anthropic / openai / langchain / crewai to be installed.

__all__ = [  # noqa: RUF022 — logical grouping (core -> adapters) over alphabetical
    "RuleSource",
    "RuleViolation",
    "build_brain_rules_block",
    "check_output",
    "is_bypassed",
    # Lazy exports — see __getattr__
    "AnthropicMiddleware",
    "OpenAIMiddleware",
    "LangChainCallback",
    "CrewAIGuard",
    "wrap_anthropic",
    "wrap_openai",
]


# name -> (submodule, attribute) for lazy adapter loading.
_LAZY_EXPORTS = {
    "AnthropicMiddleware": ("anthropic_adapter", "AnthropicMiddleware"),
    "wrap_anthropic": ("anthropic_adapter", "wrap_anthropic"),
    "OpenAIMiddleware": ("openai_adapter", "OpenAIMiddleware"),
    "wrap_openai": ("openai_adapter", "wrap_openai"),
    "LangChainCallback": ("langchain_adapter", "LangChainCallback"),
    "CrewAIGuard": ("crewai_adapter", "CrewAIGuard"),
}


def __getattr__(name: str):  # pragma: no cover - trivial dispatch
    try:
        module_name, attr_name = _LAZY_EXPORTS[name]
    except KeyError:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}",
        ) from None
    import importlib

    module = importlib.import_module(f"{__name__}.{module_name}")
    return getattr(module, attr_name)
