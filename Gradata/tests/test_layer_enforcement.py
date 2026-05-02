"""Architecture-layer import guard for src/gradata."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "gradata"

LAYER_2_ROOT = {"brain.py", "cli.py", "daemon.py", "mcp_server.py"}
LAYER_2_DIRS = {"middleware", "integrations"}
LAYER_1_DIRS = {"enhancements", "rules"}

ALLOWED_UPWARD_IMPORTS = {
    ("__init__.py", "gradata.brain"): "PUBLIC BARREL: documented top-level Brain export.",
    ("__init__.py", "gradata.enhancements.self_improvement"): "PUBLIC BARREL: graduate / parse_lessons / format_lessons / update_confidence are documented public helpers.",
    ("_core.py", "gradata.enhancements.behavioral_extractor"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.causal_chains"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.dedup"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.diff_engine"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.edit_classifier"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.instruction_cache"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.meta_rules"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.meta_rules_storage"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.metrics"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.pattern_extractor"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.pattern_integration"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.rule_canary"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.self_healing"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.self_improvement"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.self_improvement._confidence"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_core.py", "gradata.enhancements.similarity"): "DEFERRED: _core is delegated Brain behavior; moving it is >50 lines.",
    ("_mine_transcripts.py", "gradata.brain"): "LAZY-IMPORT-OK: CLI commit path opens Brain only when writing mined events.",
    ("_mine_transcripts.py", "gradata.enhancements.meta_rules_storage"): "LAZY-IMPORT-OK: CLI graduation bridge imports storage only on commit.",
    ("_scoped_brain.py", "gradata.rules.rule_engine"): "LAZY-IMPORT-OK: scoped rule injection imports ranking only when injecting.",
    ("contrib/patterns/evaluator.py", "gradata.rules.rule_context"): "LAZY-IMPORT-OK: graduated-rule adapter imports context on demand.",
    ("contrib/patterns/guardrails.py", "gradata.rules.rule_context"): "LAZY-IMPORT-OK: graduated-rule adapter imports context on demand.",
    ("contrib/patterns/orchestrator.py", "gradata.rules.scope"): "LAZY-IMPORT-OK: request classification imports scope on demand.",
    ("contrib/patterns/reflection.py", "gradata.rules.rule_context"): "LAZY-IMPORT-OK: graduated-rule adapter imports context on demand.",
}


def _layer_for(path: Path) -> int | None:
    rel = path.relative_to(ROOT)
    parts = rel.parts
    if len(parts) == 1 and parts[0] in LAYER_2_ROOT:
        return 2
    if parts[0] in LAYER_2_DIRS:
        return 2
    if parts[0] in LAYER_1_DIRS:
        return 1
    if len(parts) >= 2 and parts[:2] == ("contrib", "patterns"):
        return 0
    if len(parts) == 1 and parts[0].startswith("_"):
        return 0
    return None


def _module_path(module: str) -> Path | None:
    if not module.startswith("gradata"):
        return None
    parts = module.split(".")[1:]
    if not parts:
        return ROOT / "__init__.py"
    module_file = ROOT.joinpath(*parts).with_suffix(".py")
    if module_file.exists():
        return module_file
    package_init = ROOT.joinpath(*parts) / "__init__.py"
    if package_init.exists():
        return package_init
    return None


def _inside_type_checking(node: ast.AST) -> bool:
    parent = getattr(node, "_parent", None)
    while parent is not None:
        if isinstance(parent, ast.If) and ast.unparse(parent.test) == "TYPE_CHECKING":
            return True
        parent = getattr(parent, "_parent", None)
    return False


def _absolute_imports(tree: ast.AST) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if _inside_type_checking(node):
            continue
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.append((node.lineno, node.module))
    return imports


def test_no_unclassified_upward_layer_imports() -> None:
    failures: list[str] = []

    for path in sorted(ROOT.rglob("*.py")):
        source_layer = _layer_for(path)
        if source_layer is None:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child._parent = parent  # type: ignore[attr-defined]

        for line, module in _absolute_imports(tree):
            target = _module_path(module)
            if target is None:
                continue
            target_layer = _layer_for(target)
            if target_layer is None or target_layer <= source_layer:
                continue

            rel = path.relative_to(ROOT).as_posix()
            if (rel, module) not in ALLOWED_UPWARD_IMPORTS:
                failures.append(f"{rel}:{line} L{source_layer}->L{target_layer} imports {module}")

    assert failures == []
