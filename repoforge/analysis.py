"""Static Python inventory. Repository code is never imported."""
import ast
from pathlib import Path


def inventory(root: Path) -> dict:
    modules = {}
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if any(part.startswith(".") or part in {"venv", "node_modules"} for part in relative.parts):
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Symlinked Python files are unsupported")
        if len(modules) >= 300 or path.stat().st_size > 100_000:
            raise ValueError("Repository exceeds AST context limits")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        modules[relative.as_posix()] = {
            "functions": [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
            "imports": sorted({
                alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names
            } | {n.module or "." for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}),
        }
    return modules


def apply_edits(root: Path, edits: list[dict]) -> None:
    """Validate all exact replacements before writing any. Tests cannot be edited."""
    if not edits or len(edits) > 8:
        raise ValueError("Expected 1 to 8 source edits")
    staged = {}
    for edit in edits:
        name = edit["path"]
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
            raise ValueError("Unsafe edit path")
        if relative.parts[0] != "src" or relative.suffix != ".py":
            raise ValueError("Edits are restricted to existing src/**/*.py files")
        target = root / relative
        if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
            raise ValueError("Unsafe symlink target")
        if not target.is_file() or target.stat().st_size > 100_000:
            raise ValueError("Missing or oversized edit target")
        original = staged.get(target, target.read_text(encoding="utf-8"))
        before, after = edit["before"], edit["after"]
        if not before or original.count(before) != 1 or len(after) > 50_000:
            raise ValueError("Edit must match exactly once and fit size limit")
        updated = original.replace(before, after, 1)
        ast.parse(updated)
        staged[target] = updated
    for target, updated in staged.items():
        target.write_text(updated, encoding="utf-8")
