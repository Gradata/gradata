import ast
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "gradata"

ALLOWED_SINGLE_PASS_EXCEPTS = {
    ("src/gradata/_core.py", "brain_end_session", "ImportError"),  # optional dep ImportError
    ("src/gradata/_events.py", "emit", "ImportError"),  # optional dep ImportError
    ("src/gradata/brain.py", "Brain.__init__", "ImportError"),  # optional dep ImportError
    ("src/gradata/brain.py", "Brain.patch_rule", "ImportError"),  # optional dep ImportError
    (
        "src/gradata/enhancements/learning_pipeline.py",
        "LearningPipeline._init_stages",
        "ImportError",
    ),  # optional dep ImportError
    (
        "src/gradata/enhancements/reporting.py",
        "generate_briefing",
        "ImportError",
    ),  # optional dep ImportError
    (
        "src/gradata/enhancements/rule_pipeline.py",
        "run_rule_pipeline",
        "ImportError",
    ),  # optional dep ImportError
    (
        "src/gradata/enhancements/self_improvement/_graduation.py",
        "graduate",
        "ImportError",
    ),  # optional dep ImportError
    (
        "src/gradata/hooks/inject_brain_rules.py",
        "main",
        "ImportError",
    ),  # optional dep ImportError
    (
        "src/gradata/rules/rule_engine/_scoring.py",
        "_beta_ppf_05",
        "ImportError",
    ),  # optional dep ImportError
}


class _SinglePassExceptVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        self.scope: list[str] = []
        self.violations: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            exception_type = ast.unparse(node.type) if node.type else "bare"
            scope = ".".join(self.scope)
            allowed_key = (self.relative_path, scope, exception_type)
            if allowed_key not in ALLOWED_SINGLE_PASS_EXCEPTS:
                self.violations.append(
                    f"{self.relative_path}:{node.lineno} "
                    f"{scope or '<module>'} except {exception_type}: pass"
                )
        self.generic_visit(node)


def test_no_single_statement_except_pass_handlers() -> None:
    violations: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        relative_path = path.relative_to(SRC_ROOT.parents[1]).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        visitor = _SinglePassExceptVisitor(relative_path)
        visitor.visit(tree)
        violations.extend(visitor.violations)

    assert not violations, "Silent except-pass handlers found:\n" + "\n".join(violations)
