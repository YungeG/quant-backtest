#!/usr/bin/env python3
"""Check workspace imports against the versioned architecture policy."""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import importlib.util
import json
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SUPPORTED_POLICY_SCHEMA = 1
SUPPORTED_REPORT_SCHEMA = 1


class PolicyError(ValueError):
    """The policy cannot be interpreted safely."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(message)
        self.rule = rule
        self.message = message


@dataclass(frozen=True)
class PackagePolicy:
    id: str
    module: str
    source: str
    allowed_workspace_modules: frozenset[str]


@dataclass(frozen=True)
class ForbiddenImportRule:
    id: str
    source_packages: frozenset[str]
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    targets: tuple[str, ...]


@dataclass(frozen=True)
class DynamicImportAllowance:
    caller: str
    target_prefix: str
    reason: str


@dataclass(frozen=True)
class Policy:
    schema_version: int
    report_schema_version: int
    packages: tuple[PackagePolicy, ...]
    forbidden_import_rules: tuple[ForbiddenImportRule, ...]
    dynamic_import_allowlist: tuple[DynamicImportAllowance, ...]


@dataclass(frozen=True)
class ImportOccurrence:
    target: str | None
    explicit_targets: tuple[str, ...]
    dynamic_prefix: str | None
    line: int
    column: int
    dynamic: bool


@dataclass(frozen=True)
class Violation:
    rule: str
    source_path: str
    line: int
    column: int
    import_target: str
    message: str


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError("invalid-policy", f"{field} must be a non-empty string")
    return value


def require_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise PolicyError("invalid-policy", f"{field} must be a list of strings")
    return value


def load_policy(path: Path) -> Policy:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise PolicyError("invalid-policy", f"Cannot read policy: {error}") from error

    schema_version = raw.get("schema_version")
    if schema_version != SUPPORTED_POLICY_SCHEMA:
        raise PolicyError(
            "unsupported-policy-schema",
            f"Expected policy schema {SUPPORTED_POLICY_SCHEMA}, got {schema_version!r}",
        )
    report_schema_version = raw.get("report_schema_version")
    if report_schema_version != SUPPORTED_REPORT_SCHEMA:
        raise PolicyError(
            "unsupported-policy-schema",
            "Unsupported report schema " f"{report_schema_version!r}",
        )

    package_rows = raw.get("packages")
    if not isinstance(package_rows, list) or not package_rows:
        raise PolicyError("invalid-policy", "packages must be a non-empty array")

    packages: list[PackagePolicy] = []
    package_ids: set[str] = set()
    package_modules: set[str] = set()
    package_sources: set[str] = set()
    for index, row in enumerate(package_rows):
        if not isinstance(row, dict):
            raise PolicyError("invalid-policy", f"packages[{index}] must be a table")
        package_id = require_string(row.get("id"), f"packages[{index}].id")
        module = require_string(row.get("module"), f"packages[{index}].module")
        source = require_string(row.get("source"), f"packages[{index}].source")
        allowed = frozenset(
            require_string_list(
                row.get("allowed_workspace_modules"),
                f"packages[{index}].allowed_workspace_modules",
            )
        )
        if package_id in package_ids or module in package_modules or source in package_sources:
            raise PolicyError(
                "invalid-policy",
                f"Duplicate package id, module, or source at packages[{index}]",
            )
        package_ids.add(package_id)
        package_modules.add(module)
        package_sources.add(source)
        packages.append(PackagePolicy(package_id, module, source, allowed))

    for package in packages:
        unknown = package.allowed_workspace_modules - package_modules
        if unknown:
            raise PolicyError(
                "invalid-policy",
                f"Package {package.id} allows unknown modules: {sorted(unknown)}",
            )
        if package.module in package.allowed_workspace_modules:
            raise PolicyError(
                "invalid-policy",
                f"Package {package.id} must not list itself as an allowed dependency",
            )

    forbidden_rules: list[ForbiddenImportRule] = []
    rule_ids: set[str] = set()
    for index, row in enumerate(raw.get("forbidden_import_rules", [])):
        if not isinstance(row, dict):
            raise PolicyError(
                "invalid-policy", f"forbidden_import_rules[{index}] must be a table"
            )
        rule_id = require_string(row.get("id"), f"forbidden_import_rules[{index}].id")
        source_packages = frozenset(
            require_string_list(
                row.get("source_packages"),
                f"forbidden_import_rules[{index}].source_packages",
            )
        )
        include = tuple(
            require_string_list(
                row.get("include"), f"forbidden_import_rules[{index}].include"
            )
        )
        exclude = tuple(
            require_string_list(
                row.get("exclude"), f"forbidden_import_rules[{index}].exclude"
            )
        )
        targets = tuple(
            require_string_list(
                row.get("targets"), f"forbidden_import_rules[{index}].targets"
            )
        )
        if rule_id in rule_ids:
            raise PolicyError("invalid-policy", f"Duplicate rule id: {rule_id}")
        unknown_packages = source_packages - package_ids
        if unknown_packages:
            raise PolicyError(
                "invalid-policy",
                f"Rule {rule_id} references unknown packages: {sorted(unknown_packages)}",
            )
        rule_ids.add(rule_id)
        forbidden_rules.append(
            ForbiddenImportRule(rule_id, source_packages, include, exclude, targets)
        )

    dynamic = raw.get("dynamic_imports")
    if not isinstance(dynamic, dict):
        raise PolicyError("invalid-policy", "dynamic_imports must be a table")
    nonliteral_default = dynamic.get("nonliteral_default")
    if nonliteral_default != "deny":
        raise PolicyError(
            "invalid-policy", "dynamic_imports.nonliteral_default must be 'deny'"
        )

    allowances: list[DynamicImportAllowance] = []
    allowance_callers: set[str] = set()
    for index, row in enumerate(raw.get("dynamic_import_allowlist", [])):
        if not isinstance(row, dict):
            raise PolicyError(
                "invalid-policy", f"dynamic_import_allowlist[{index}] must be a table"
            )
        caller = require_string(
            row.get("caller"), f"dynamic_import_allowlist[{index}].caller"
        )
        target_prefix = require_string(
            row.get("target_prefix"),
            f"dynamic_import_allowlist[{index}].target_prefix",
        )
        reason = require_string(
            row.get("reason"), f"dynamic_import_allowlist[{index}].reason"
        )
        if caller in allowance_callers:
            raise PolicyError(
                "invalid-policy", f"Duplicate dynamic import caller: {caller}"
            )
        allowance_callers.add(caller)
        allowances.append(DynamicImportAllowance(caller, target_prefix, reason))

    return Policy(
        schema_version=schema_version,
        report_schema_version=report_schema_version,
        packages=tuple(packages),
        forbidden_import_rules=tuple(forbidden_rules),
        dynamic_import_allowlist=tuple(allowances),
    )


def target_has_prefix(target: str, prefix: str) -> bool:
    return target == prefix or target.startswith(prefix + ".")


def path_matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def module_context(source_root: Path, source_path: Path) -> tuple[str, str]:
    relative = source_path.relative_to(source_root)
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        module = ".".join(parts[:-1])
        package = module
    else:
        module = ".".join(parts)
        package = ".".join(parts[:-1])
    return module, package


def resolve_from_import(module: str | None, level: int, package: str) -> str:
    if level == 0:
        return module or ""
    relative_name = "." * level + (module or "")
    try:
        return importlib.util.resolve_name(relative_name, package)
    except (ImportError, ValueError):
        return relative_name


def dynamic_call_names(
    tree: ast.AST,
) -> tuple[set[str], set[str], set[str], set[int]]:
    importlib_names = {"importlib"}
    builtins_names = {"builtins", "__builtins__"}
    import_function_names: set[str] = {"__import__"}
    nodes = tuple(ast.walk(tree))

    def target_names(target: ast.expr) -> tuple[str, ...]:
        if isinstance(target, ast.Name):
            return (target.id,)
        if isinstance(target, ast.Starred):
            return target_names(target.value)
        if isinstance(target, (ast.Tuple, ast.List)):
            return tuple(
                name for value in target.elts for name in target_names(value)
            )
        return ()

    def is_importlib_module(expression: ast.expr) -> bool:
        return isinstance(expression, ast.Name) and expression.id in importlib_names

    def is_builtins_module(expression: ast.expr) -> bool:
        return isinstance(expression, ast.Name) and expression.id in builtins_names

    def is_dynamic(expression: ast.expr) -> bool:
        if isinstance(expression, ast.Name):
            return expression.id in import_function_names
        if isinstance(expression, ast.Attribute):
            return expression.attr in {"import_module", "__import__"}
        if isinstance(expression, ast.Subscript):
            return (
                isinstance(expression.slice, ast.Constant)
                and expression.slice.value == "__import__"
            )
        if isinstance(expression, ast.Call):
            return (
                isinstance(expression.func, ast.Name)
                and expression.func.id == "getattr"
                and bool(expression.args)
                and is_builtins_module(expression.args[0])
            )
        if isinstance(expression, ast.NamedExpr):
            return is_dynamic(expression.value)
        if isinstance(expression, (ast.Tuple, ast.List, ast.Set)):
            return any(is_dynamic(value) for value in expression.elts)
        return False

    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib":
                    importlib_names.add(alias.asname or alias.name)
                elif alias.name == "builtins":
                    builtins_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local = alias.asname or alias.name
                if alias.name == "import_module":
                    import_function_names.add(local)
                elif alias.name == "__import__":
                    import_function_names.add(local)
                elif alias.name == "__builtins__":
                    builtins_names.add(local)

    changed = True
    while changed:
        changed = False
        for node in nodes:
            targets: tuple[str, ...] = ()
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets = tuple(
                    name
                    for target in node.targets
                    for name in target_names(target)
                )
                value = node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets = target_names(node.target)
                value = node.value
            elif isinstance(node, ast.NamedExpr):
                targets = target_names(node.target)
                value = node.value
            if value is not None:
                if is_dynamic(value):
                    before = len(import_function_names)
                    import_function_names.update(targets)
                    changed |= len(import_function_names) != before
                if is_importlib_module(value):
                    before = len(importlib_names)
                    importlib_names.update(targets)
                    changed |= len(importlib_names) != before
                if is_builtins_module(value):
                    before = len(builtins_names)
                    builtins_names.update(targets)
                    changed |= len(builtins_names) != before
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                positional = (*node.args.posonlyargs, *node.args.args)
                for argument, default in zip(
                    reversed(positional),
                    reversed(node.args.defaults),
                    strict=False,
                ):
                    if is_dynamic(default) and argument.arg not in import_function_names:
                        import_function_names.add(argument.arg)
                        changed = True
                for argument, kw_default in zip(
                    node.args.kwonlyargs,
                    node.args.kw_defaults,
                    strict=True,
                ):
                    if (
                        kw_default is not None
                        and is_dynamic(kw_default)
                        and argument.arg not in import_function_names
                    ):
                        import_function_names.add(argument.arg)
                        changed = True

    dynamic_call_ids = {
        id(node)
        for node in nodes
        if isinstance(node, ast.Call) and is_dynamic(node.func)
    }
    return (
        importlib_names,
        builtins_names,
        import_function_names,
        dynamic_call_ids,
    )


def infer_dynamic_prefix(expression: ast.expr) -> str | None:
    if isinstance(expression, ast.JoinedStr):
        prefix = ""
        for value in expression.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                prefix += value.value
            else:
                break
        return prefix.rstrip(".") or None
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        if isinstance(expression.left, ast.Constant) and isinstance(
            expression.left.value, str
        ):
            return expression.left.value.rstrip(".") or None
        return infer_dynamic_prefix(expression.left)
    return None


def collect_imports(source_root: Path, source_path: Path) -> list[ImportOccurrence]:
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    _, current_package = module_context(source_root, source_path)
    dynamic_call_ids = dynamic_call_names(tree)[3]
    occurrences: list[ImportOccurrence] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            occurrences.extend(
                ImportOccurrence(
                    alias.name,
                    (alias.name,),
                    None,
                    node.lineno,
                    node.col_offset,
                    False,
                )
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            target = resolve_from_import(node.module, node.level, current_package)
            if node.module is None and node.level and target:
                occurrences.extend(
                    ImportOccurrence(
                        f"{target}.{alias.name}",
                        (f"{target}.{alias.name}",),
                        None,
                        node.lineno,
                        node.col_offset,
                        False,
                    )
                    for alias in node.names
                    if alias.name != "*"
                )
            elif target:
                explicit_targets = (target,) + tuple(
                    f"{target}.{alias.name}"
                    for alias in node.names
                    if alias.name != "*"
                )
                occurrences.append(
                    ImportOccurrence(
                        target,
                        explicit_targets,
                        None,
                        node.lineno,
                        node.col_offset,
                        False,
                    )
                )
        elif isinstance(node, ast.Call):
            if id(node) in dynamic_call_ids:
                target = None
                dynamic_prefix = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant) and isinstance(
                        node.args[0].value, str
                    ):
                        target = node.args[0].value
                    else:
                        dynamic_prefix = infer_dynamic_prefix(node.args[0])
                occurrences.append(
                    ImportOccurrence(
                        target,
                        (target,) if target else (),
                        dynamic_prefix,
                        node.lineno,
                        node.col_offset,
                        True,
                    )
                )

    return sorted(
        occurrences,
        key=lambda item: (
            item.line,
            item.column,
            item.target or "",
            item.explicit_targets,
            item.dynamic_prefix or "",
            item.dynamic,
        ),
    )


def workspace_package_for_target(
    packages: tuple[PackagePolicy, ...], target: str
) -> PackagePolicy | None:
    matches = [package for package in packages if target_has_prefix(target, package.module)]
    if not matches:
        return None
    return max(matches, key=lambda package: len(package.module))


def explicit_rule_violations(
    policy: Policy,
    source_package: PackagePolicy,
    source_relative: str,
    repository_relative: str,
    occurrence: ImportOccurrence,
) -> list[Violation]:
    if occurrence.target is None:
        raise ValueError("explicit rule requires a resolved import target")
    violations: list[Violation] = []
    for rule in policy.forbidden_import_rules:
        if source_package.id not in rule.source_packages:
            continue
        if not path_matches(source_relative, rule.include):
            continue
        if rule.exclude and path_matches(source_relative, rule.exclude):
            continue
        matched_target = next(
            (
                candidate
                for candidate in occurrence.explicit_targets
                if any(target_has_prefix(candidate, prefix) for prefix in rule.targets)
            ),
            None,
        )
        if matched_target is None:
            continue
        violations.append(
            Violation(
                rule=rule.id,
                source_path=repository_relative,
                line=occurrence.line,
                column=occurrence.column,
                import_target=matched_target,
                message=f"{source_package.id} must not import {matched_target}",
            )
        )
    return violations


def check_occurrence(
    policy: Policy,
    source_package: PackagePolicy,
    source_relative: str,
    repository_relative: str,
    occurrence: ImportOccurrence,
) -> list[Violation]:
    if occurrence.dynamic and occurrence.target is None:
        allowed = any(
            allowance.caller == repository_relative
            and occurrence.dynamic_prefix is not None
            and target_has_prefix(
                occurrence.dynamic_prefix, allowance.target_prefix
            )
            for allowance in policy.dynamic_import_allowlist
        )
        if allowed:
            return []
        dynamic_target = (
            f"<dynamic:{occurrence.dynamic_prefix}>"
            if occurrence.dynamic_prefix
            else "<dynamic>"
        )
        return [
            Violation(
                rule="undeclared-dynamic-import",
                source_path=repository_relative,
                line=occurrence.line,
                column=occurrence.column,
                import_target=dynamic_target,
                message=(
                    "Non-literal dynamic import requires an inferable prefix and "
                    "an exact caller/prefix policy allowance"
                ),
            )
        ]

    if occurrence.target is None:
        return []
    if occurrence.target.startswith("."):
        return [
            Violation(
                rule="undeclared-dynamic-import",
                source_path=repository_relative,
                line=occurrence.line,
                column=occurrence.column,
                import_target=occurrence.target,
                message="Relative dynamic import could not be resolved safely",
            )
        ]

    explicit = explicit_rule_violations(
        policy,
        source_package,
        source_relative,
        repository_relative,
        occurrence,
    )
    if explicit:
        return explicit

    target_package = workspace_package_for_target(policy.packages, occurrence.target)
    if target_package is None or target_package.id == source_package.id:
        return []
    if target_package.module not in source_package.allowed_workspace_modules:
        return [
            Violation(
                rule="forbidden-workspace-import",
                source_path=repository_relative,
                line=occurrence.line,
                column=occurrence.column,
                import_target=occurrence.target,
                message=(
                    f"{source_package.id} may not depend on {target_package.id}"
                ),
            )
        ]
    if occurrence.target != target_package.module:
        return [
            Violation(
                rule="cross-package-internal-import",
                source_path=repository_relative,
                line=occurrence.line,
                column=occurrence.column,
                import_target=occurrence.target,
                message=(
                    f"Cross-package imports must use public root "
                    f"{target_package.module}"
                ),
            )
        ]
    return []


def _source_read_violation(
    repository_relative: str,
    error: SyntaxError | UnicodeError | OSError,
) -> Violation:
    line = error.lineno if isinstance(error, SyntaxError) else 0
    column = error.offset if isinstance(error, SyntaxError) else 0
    return Violation(
        rule="python-source-unreadable",
        source_path=repository_relative,
        line=line or 0,
        column=column or 0,
        import_target="<source>",
        message=str(error),
    )


def check_repository(root: Path, policy: Policy) -> tuple[int, list[Violation]]:
    violations: list[Violation] = []
    files_scanned = 0
    for package in sorted(policy.packages, key=lambda item: item.id):
        source_root = root / package.source
        if not source_root.is_dir():
            continue
        for source_path in sorted(source_root.rglob("*.py")):
            files_scanned += 1
            repository_relative = source_path.relative_to(root).as_posix()
            source_relative = source_path.relative_to(source_root).as_posix()
            try:
                occurrences = collect_imports(source_root, source_path)
            except SyntaxError as error:
                violations.append(_source_read_violation(repository_relative, error))
                continue
            except UnicodeError as error:
                violations.append(_source_read_violation(repository_relative, error))
                continue
            except OSError as error:
                violations.append(_source_read_violation(repository_relative, error))
                continue
            for occurrence in occurrences:
                violations.extend(
                    check_occurrence(
                        policy,
                        package,
                        source_relative,
                        repository_relative,
                        occurrence,
                    )
                )

    return files_scanned, sorted(
        violations,
        key=lambda violation: (
            violation.rule,
            violation.source_path,
            violation.line,
            violation.import_target,
            violation.column,
        ),
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def invalid_policy_report(policy_path: Path, error: PolicyError) -> dict[str, Any]:
    policy_hash = sha256(policy_path) if policy_path.is_file() else None
    violation = Violation(
        rule=error.rule,
        source_path="<policy>",
        line=0,
        column=0,
        import_target="<policy>",
        message=error.message,
    )
    return {
        "files_scanned": 0,
        "policy_sha256": policy_hash,
        "policy_schema_version": None,
        "report_schema_version": SUPPORTED_REPORT_SCHEMA,
        "status": "invalid-policy",
        "violations": [asdict(violation)],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = args.root.resolve()
    policy_path = args.policy.resolve()
    report_path = args.report.resolve()

    try:
        policy = load_policy(policy_path)
    except PolicyError as error:
        write_report(report_path, invalid_policy_report(policy_path, error))
        print(error.message, file=sys.stderr)
        return 2

    files_scanned, violations = check_repository(root, policy)
    payload = {
        "files_scanned": files_scanned,
        "policy_sha256": sha256(policy_path),
        "policy_schema_version": policy.schema_version,
        "report_schema_version": policy.report_schema_version,
        "status": "failed" if violations else "passed",
        "violations": [asdict(violation) for violation in violations],
    }
    write_report(report_path, payload)

    if violations:
        for violation in violations:
            print(
                f"{violation.source_path}:{violation.line}: "
                f"{violation.rule}: {violation.import_target}",
                file=sys.stderr,
            )
        return 1
    print(f"Import boundaries passed ({files_scanned} files scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
