"""Architecture boundary tests for the modular monolith."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FORBIDDEN_IMPORTS = {
    "src.domain": ("src.adapters", "src.infrastructure"),
    "src.application": ("src.adapters", "src.infrastructure"),
}


def module_name(path: Path) -> str:
    """Return the Python module name for a source file."""
    relative = path.relative_to(ROOT).with_suffix("")
    return ".".join(relative.parts)


def absolute_from_import(current_module: str, level: int, module: str) -> str:
    """Resolve an ImportFrom node to an absolute module name."""
    if level == 0:
        return module

    package_parts = current_module.split(".")[:-1]
    anchor = package_parts[: len(package_parts) - level + 1]
    if module:
        anchor.extend(module.split("."))
    return ".".join(anchor)


def imports_in(path: Path) -> set[str]:
    """Collect imported module names from a Python file."""
    current_module = module_name(path)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(
                absolute_from_import(
                    current_module,
                    node.level,
                    node.module or "",
                )
            )
    return imports


def test_domain_and_application_do_not_import_outer_layers() -> None:
    """Core layers must stay reusable by CLI and future HTTP adapters."""
    violations: list[str] = []
    for path in SRC.rglob("*.py"):
        module = module_name(path)
        for inner_prefix, forbidden_prefixes in FORBIDDEN_IMPORTS.items():
            if not module.startswith(inner_prefix):
                continue
            for imported in imports_in(path):
                for forbidden in forbidden_prefixes:
                    is_forbidden = (
                        imported == forbidden
                        or imported.startswith(f"{forbidden}.")
                    )
                    if is_forbidden:
                        violations.append(
                            f"{module} imports outer layer {imported}"
                        )

    assert violations == []


def adapter_family(module: str) -> str:
    """Return the top-level adapter family for one module."""
    return ".".join(module.split(".")[:3])


def test_adapters_do_not_import_peer_adapters() -> None:
    """CLI and HTTP families must meet only through application code."""
    violations: list[str] = []
    for path in (SRC / "adapters").rglob("*.py"):
        module = module_name(path)
        family = adapter_family(module)
        for imported in imports_in(path):
            if (
                imported.startswith("src.adapters.")
                and adapter_family(imported) != family
            ):
                violations.append(f"{module} imports peer adapter {imported}")

    assert violations == []
