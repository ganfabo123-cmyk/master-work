"""Static format checks for Agent-owned tool files."""

from __future__ import annotations

import ast
from pathlib import Path


_INFRASTRUCTURE_FILES = {"__init__.py", "base.py", "registry.py", "utils.py", "check_tool_files.py"}


def _is_annotated_field(annotation: ast.expr | None) -> bool:
    if not isinstance(annotation, ast.Subscript) or not isinstance(annotation.value, ast.Name) or annotation.value.id != "Annotated":
        return False
    if not isinstance(annotation.slice, ast.Tuple) or len(annotation.slice.elts) != 2:
        return False
    value_type, field = annotation.slice.elts
    if isinstance(value_type, ast.Name) and value_type.id == "Any":
        return False
    if not isinstance(field, ast.Call) or not isinstance(field.func, ast.Name) or field.func.id != "Field":
        return False
    return any(
        keyword.arg == "description" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str) and bool(keyword.value.value.strip())
        for keyword in field.keywords
    )


def _check_method(path: Path, class_name: str, method: ast.FunctionDef) -> list[str]:
    errors: list[str] = []
    if not ast.get_docstring(method):
        errors.append(f"{path.name}:{class_name}.{method.name} 缺少 docstring")
    if method.returns is None:
        errors.append(f"{path.name}:{class_name}.{method.name} 缺少返回类型标注")
    parameters = (*method.args.posonlyargs, *method.args.args, *method.args.kwonlyargs)
    for parameter in parameters:
        if parameter.arg == "self":
            continue
        if not _is_annotated_field(parameter.annotation):
            errors.append(f"{path.name}:{class_name}.{method.name}.{parameter.arg} 必须使用 Annotated[类型, Field(description=...)]")
    return errors


def check_tool_files(root: Path | None = None) -> tuple[str, ...]:
    """Return all tool-file format violations below the tools package."""
    tools_root = root or Path(__file__).resolve().parent
    errors: list[str] = []
    for path in sorted(tools_root.glob("*.py")):
        if path.name in _INFRASTRUCTURE_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name.endswith("Tools")]
        if not classes:
            errors.append(f"{path.name} 必须定义至少一个以 Tools 结尾的工具类")
            continue
        for class_node in classes:
            base_names = [base.id for base in class_node.bases if isinstance(base, ast.Name)]
            if not any(name.endswith("Tools") for name in base_names):
                errors.append(f"{path.name}:{class_node.name} 必须继承 BaseAgentTools、LongTermMemoryTools 或其他工具类")
            for method in class_node.body:
                if isinstance(method, ast.FunctionDef) and method.name != "__init__" and not method.name.startswith("_"):
                    errors.extend(_check_method(path, class_node.name, method))
    return tuple(errors)


def main() -> int:
    """Print violations and return a process exit code for CI or local use."""
    errors = check_tool_files()
    if errors:
        print("\n".join(errors))
        return 1
    print("tool file format check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
