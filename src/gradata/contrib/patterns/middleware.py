"""
Middleware Chain — Composable ordered middleware with anchor positioning.
=========================================================================
Adapted from: deer-flow (bytedance/deer-flow) agents/factory.py

Provides a pluggable middleware chain for the learning pipeline and
brain operations. Each middleware can hook into before/after execution
points. Middlewares are ordered via anchor-based positioning (Next/Prev)
with circular dependency detection.

This is architecturally cleaner than a flat hooks list because:
- Middlewares declare their relative position (not absolute index)
- Circular dependencies are detected at registration time
- Each middleware is a self-contained class with typed lifecycle hooks

Usage::

    from gradata.contrib.patterns.middleware import (
        Middleware, MiddlewareChain, MiddlewareContext,
    )

    class LoggingMiddleware(Middleware):
        name = "logging"

        def before(self, ctx: MiddlewareContext) -> MiddlewareContext:
            print(f"Before: {ctx.operation}")
            return ctx

        def after(self, ctx: MiddlewareContext) -> MiddlewareContext:
            print(f"After: {ctx.operation}, result={ctx.result}")
            return ctx

    chain = MiddlewareChain()
    chain.add(LoggingMiddleware())
    result = chain.execute("correct", data={"draft": "...", "final": "..."})
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Middleware",
    "MiddlewareContext",
    "MiddlewareChain",
    "MiddlewareError",
]


class MiddlewareError(Exception):
    """Raised when middleware chain has configuration errors."""
    pass


@dataclass
class MiddlewareContext:
    """Context passed through the middleware chain.

    Mutable — each middleware can modify and pass along.

    Attributes:
        operation: Name of the operation being executed (e.g. "correct", "search").
        data: Arbitrary data dict for the operation.
        result: Result from the operation (populated after execution).
        halted: If True, skip remaining middlewares and return immediately.
        halt_reason: Why the chain was halted.
        metadata: Middleware-contributed metadata.
        errors: Errors collected during chain execution.
    """
    operation: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    halted: bool = False
    halt_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class Middleware:
    """Base class for middleware in the chain.

    Subclass and override ``before()`` and/or ``after()`` to add
    cross-cutting behavior. Set ``name`` for identification.

    Anchor positioning:
        after_middleware: Name of middleware this should follow.
        before_middleware: Name of middleware this should precede.
        If neither is set, middleware is appended to the end.
    """
    name: str = "unnamed"
    after_middleware: str = ""   # Insert after this middleware
    before_middleware: str = ""  # Insert before this middleware

    def before(self, ctx: MiddlewareContext) -> MiddlewareContext:
        """Called before the operation executes.

        Return the (possibly modified) context. Set ctx.halted=True
        to stop the chain.
        """
        return ctx

    def after(self, ctx: MiddlewareContext) -> MiddlewareContext:
        """Called after the operation executes.

        Return the (possibly modified) context. Can inspect ctx.result.
        """
        return ctx

    def on_error(self, ctx: MiddlewareContext, error: Exception) -> MiddlewareContext:
        """Called when an error occurs during the operation.

        Default: appends error to ctx.errors and returns.
        Override for custom error handling.
        """
        ctx.errors.append(f"[{self.name}] {error}")
        return ctx

    def __repr__(self) -> str:
        return f"Middleware({self.name!r})"


class MiddlewareChain:
    """Ordered chain of middlewares with anchor-based insertion.

    Middlewares execute in order: all ``before()`` hooks run first,
    then the operation, then all ``after()`` hooks in reverse order
    (onion model).

    Anchor positioning:
        - Set ``after_middleware`` to position after a named middleware
        - Set ``before_middleware`` to position before a named middleware
        - If neither is set, middleware is appended to the end
        - Conflicting/circular anchors raise MiddlewareError
    """

    def __init__(self) -> None:
        self._middlewares: list[Middleware] = []
        self._name_index: dict[str, int] = {}

    def add(self, middleware: Middleware) -> None:
        """Add a middleware to the chain with anchor-based positioning.

        Args:
            middleware: The middleware to add.

        Raises:
            MiddlewareError: If anchors reference unknown or circular deps.
        """
        if middleware.name in self._name_index:
            raise MiddlewareError(
                f"Middleware '{middleware.name}' already registered"
            )

        if middleware.after_middleware and middleware.before_middleware:
            raise MiddlewareError(
                f"Middleware '{middleware.name}' cannot specify both "
                f"after_middleware and before_middleware"
            )

        if middleware.after_middleware:
            anchor = middleware.after_middleware
            if anchor not in self._name_index:
                raise MiddlewareError(
                    f"Middleware '{middleware.name}' wants to follow "
                    f"'{anchor}' which is not registered"
                )
            idx = self._name_index[anchor] + 1
            self._middlewares.insert(idx, middleware)
        elif middleware.before_middleware:
            anchor = middleware.before_middleware
            if anchor not in self._name_index:
                raise MiddlewareError(
                    f"Middleware '{middleware.name}' wants to precede "
                    f"'{anchor}' which is not registered"
                )
            idx = self._name_index[anchor]
            self._middlewares.insert(idx, middleware)
        else:
            self._middlewares.append(middleware)

        # Rebuild name index after insertion
        self._rebuild_index()

    def remove(self, name: str) -> bool:
        """Remove a middleware by name. Returns True if found."""
        if name not in self._name_index:
            return False
        idx = self._name_index[name]
        self._middlewares.pop(idx)
        self._rebuild_index()
        return True

    def execute(
        self,
        operation: str,
        data: dict[str, Any] | None = None,
        executor: Any | None = None,
    ) -> MiddlewareContext:
        """Execute the middleware chain around an operation.

        Args:
            operation: Name of the operation.
            data: Data dict for the operation.
            executor: Optional callable to run as the core operation.
                Called between before() and after() hooks.

        Returns:
            MiddlewareContext with results and metadata.
        """
        ctx = MiddlewareContext(operation=operation, data=data or {})

        # Phase 1: before() hooks (forward order)
        for mw in self._middlewares:
            try:
                ctx = mw.before(ctx)
                if ctx.halted:
                    return ctx
            except Exception as e:
                ctx = mw.on_error(ctx, e)
                if ctx.halted:
                    return ctx

        # Phase 2: Execute the core operation
        if executor is not None:
            try:
                ctx.result = executor(ctx)
            except Exception as e:
                ctx.errors.append(f"[executor] {e}")

        # Phase 3: after() hooks (reverse order — onion model)
        for mw in reversed(self._middlewares):
            try:
                ctx = mw.after(ctx)
            except Exception as e:
                ctx = mw.on_error(ctx, e)

        return ctx

    @property
    def middleware_names(self) -> list[str]:
        """Return ordered list of middleware names."""
        return [mw.name for mw in self._middlewares]

    @property
    def count(self) -> int:
        """Number of middlewares in the chain."""
        return len(self._middlewares)

    def get(self, name: str) -> Middleware | None:
        """Get a middleware by name."""
        idx = self._name_index.get(name)
        if idx is None:
            return None
        return self._middlewares[idx]

    def stats(self) -> dict[str, Any]:
        """Return chain statistics."""
        return {
            "count": self.count,
            "names": self.middleware_names,
        }

    def _rebuild_index(self) -> None:
        """Rebuild the name-to-index mapping."""
        self._name_index = {
            mw.name: i for i, mw in enumerate(self._middlewares)
        }
