"""Runtime middleware adapters for non-Claude-Code environments.

Gradata's hooks only fire inside Claude Code. For direct-SDK agents
(raw OpenAI SDK, raw Anthropic SDK, LangChain, CrewAI) this subpackage
provides runtime wrappers that inject learned rules into system prompts
and enforce RULE-tier patterns on outputs.

Quick start:

    from anthropic import Anthropic
    from gradata.middleware import wrap_anthropic

    client = wrap_anthropic(Anthropic(), brain_path="./brain")
    # All client.messages.create(...) calls now get rules injected.

The adapters share a common :class:`RuleSource` that reads from the same
``lessons.md`` + brain database that Claude Code hooks use, so behaviour
is consistent across environments.

Environment overrides:
    GRADATA_BYPASS=1 — disables all injection and enforcement (emergency kill switch).

Optional deps:
    - AnthropicMiddleware / wrap_anthropic  -> ``anthropic``
    - OpenAIMiddleware / wrap_openai        -> ``openai``
    - LangChainCallback                     -> ``langchain-core``
    - CrewAIGuard                           -> works with plain CrewAI guardrails

Importing an adapter without its optional dep raises a clear ImportError
with the install hint.
"""

from __future__ import annotations

from gradata.middleware._core import (
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
