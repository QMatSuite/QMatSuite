#!/usr/bin/env python3
"""
API Surface Audit Tool

Enumerates all public entrypoints in quantumvitas.api and computes usage counts.
Used for API slimming progress tracking per API_CONSTITUTION.md.

Usage:
    python tools/api_surface_audit.py

Output: Machine-readable JSON + human summary to stdout.
"""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class AuditResult:
    """Audit result for a single entrypoint."""
    name: str
    category: str  # dto, error, utils, service_static, service_nested, api_init
    module: str
    daemon_refs: int = 0
    cli_refs: int = 0
    test_refs: int = 0

    @property
    def total_refs(self) -> int:
        return self.daemon_refs + self.cli_refs

    @property
    def is_unused(self) -> bool:
        return self.daemon_refs == 0 and self.cli_refs == 0


@dataclass
class AuditSummary:
    """Summary of all audit results."""
    total_entrypoints: int = 0
    by_category: dict = field(default_factory=dict)
    unused_count: int = 0
    daemon_only_count: int = 0
    cli_only_count: int = 0
    both_count: int = 0
    entrypoints: list = field(default_factory=list)


def get_repo_root() -> Path:
    """Get repository root."""
    return Path(__file__).parent.parent


def count_refs(pattern: str, search_dir: Path) -> int:
    """Count references to a pattern in a directory using grep."""
    try:
        result = subprocess.run(
            ["grep", "-r", "-l", pattern, str(search_dir)],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            # Count occurrences, not just files
            result2 = subprocess.run(
                ["grep", "-r", "-c", pattern, str(search_dir)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result2.returncode == 0:
                total = 0
                for line in result2.stdout.strip().split('\n'):
                    if ':' in line and not '__pycache__' in line:
                        try:
                            count = int(line.split(':')[-1])
                            total += count
                        except ValueError:
                            pass
                return total
        return 0
    except Exception:
        return 0


def extract_utils_functions(utils_path: Path) -> list[str]:
    """Extract all public function names from utils.py."""
    functions = []
    content = utils_path.read_text()

    # Use regex to find function definitions
    pattern = r'^def ([a-z_][a-z0-9_]*)\('
    for match in re.finditer(pattern, content, re.MULTILINE):
        func_name = match.group(1)
        if not func_name.startswith('_'):
            functions.append(func_name)

    # Also find class re-exports
    class_pattern = r'^from .+ import .+\b([A-Z][a-zA-Z0-9]+)\b'
    for match in re.finditer(class_pattern, content, re.MULTILINE):
        class_name = match.group(1)
        if class_name not in ['Path', 'Any', 'Optional']:
            functions.append(class_name)

    return functions


def extract_service_methods(service_path: Path) -> tuple[list[str], list[str]]:
    """Extract static and nested service methods from service.py."""
    content = service_path.read_text()

    static_methods = []
    nested_methods = []

    # Parse AST for accurate method extraction
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [], []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name == 'QVService':
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        # Check for @staticmethod decorator
                        is_static = any(
                            isinstance(d, ast.Name) and d.id == 'staticmethod'
                            for d in item.decorator_list
                        )
                        if is_static and not item.name.startswith('_'):
                            static_methods.append(item.name)
                    elif isinstance(item, ast.ClassDef):
                        # Nested service class
                        for nested_item in item.body:
                            if isinstance(nested_item, ast.FunctionDef):
                                if not nested_item.name.startswith('_'):
                                    nested_methods.append(f"{item.name}.{nested_item.name}")

    return static_methods, nested_methods


def extract_errors(errors_path: Path) -> list[str]:
    """Extract error class names from errors.py."""
    content = errors_path.read_text()
    errors = []

    pattern = r'^class ([A-Z][a-zA-Z]+Error)\('
    for match in re.finditer(pattern, content, re.MULTILINE):
        errors.append(match.group(1))

    # Add base APIError
    if 'class APIError(' in content:
        errors.insert(0, 'APIError')

    return errors


def extract_dtos(types_dir: Path) -> list[str]:
    """Extract DTO class names from types/ directory."""
    dtos = []

    for py_file in types_dir.glob('*.py'):
        if py_file.name.startswith('_'):
            continue
        content = py_file.read_text()

        # Find dataclass or class definitions that look like DTOs
        pattern = r'^class ([A-Z][a-zA-Z]+(?:DTO|Summary|Ref)?)\('
        for match in re.finditer(pattern, content, re.MULTILINE):
            class_name = match.group(1)
            if class_name not in ['Path', 'Any', 'Optional']:
                dtos.append(class_name)

    return dtos


def extract_init_exports(init_path: Path) -> list[str]:
    """Extract exports from __init__.py that aren't errors/DTOs."""
    content = init_path.read_text()
    exports = []

    # Find function definitions
    pattern = r'^def ([a-z_][a-z0-9_]*)\('
    for match in re.finditer(pattern, content, re.MULTILINE):
        exports.append(match.group(1))

    return exports


def run_audit() -> AuditSummary:
    """Run the full API surface audit."""
    repo_root = get_repo_root()
    api_dir = repo_root / 'src' / 'quantumvitas' / 'api'
    daemon_dir = repo_root / 'src' / 'quantumvitas' / 'daemon'
    cli_dir = repo_root / 'src' / 'quantumvitas' / 'cli'
    tests_dir = repo_root / 'tests'

    summary = AuditSummary()
    summary.by_category = {
        'utils': 0,
        'service_static': 0,
        'service_nested': 0,
        'errors': 0,
        'dtos': 0,
        'api_init': 0,
    }

    # 1. Utils functions
    utils_path = api_dir / 'utils.py'
    if utils_path.exists():
        utils_funcs = extract_utils_functions(utils_path)
        for func in utils_funcs:
            result = AuditResult(
                name=func,
                category='utils',
                module='api.utils',
                daemon_refs=count_refs(func, daemon_dir),
                cli_refs=count_refs(func, cli_dir),
                test_refs=count_refs(func, tests_dir),
            )
            summary.entrypoints.append(result)
            summary.by_category['utils'] += 1

    # 2. Service methods
    service_path = api_dir / 'service.py'
    if service_path.exists():
        static_methods, nested_methods = extract_service_methods(service_path)

        for method in static_methods:
            result = AuditResult(
                name=method,
                category='service_static',
                module='api.service.QVService',
                daemon_refs=count_refs(method, daemon_dir),
                cli_refs=count_refs(method, cli_dir),
                test_refs=count_refs(method, tests_dir),
            )
            summary.entrypoints.append(result)
            summary.by_category['service_static'] += 1

        for method in nested_methods:
            short_name = method.split('.')[-1]
            result = AuditResult(
                name=method,
                category='service_nested',
                module='api.service.QVService',
                daemon_refs=count_refs(short_name, daemon_dir),
                cli_refs=count_refs(short_name, cli_dir),
                test_refs=count_refs(short_name, tests_dir),
            )
            summary.entrypoints.append(result)
            summary.by_category['service_nested'] += 1

    # 3. Errors
    errors_path = api_dir / 'errors.py'
    if errors_path.exists():
        errors = extract_errors(errors_path)
        for err in errors:
            result = AuditResult(
                name=err,
                category='errors',
                module='api.errors',
                daemon_refs=count_refs(err, daemon_dir),
                cli_refs=count_refs(err, cli_dir),
                test_refs=count_refs(err, tests_dir),
            )
            summary.entrypoints.append(result)
            summary.by_category['errors'] += 1

    # 4. DTOs
    types_dir = api_dir / 'types'
    if types_dir.exists():
        dtos = extract_dtos(types_dir)
        for dto in dtos:
            result = AuditResult(
                name=dto,
                category='dtos',
                module='api.types',
                daemon_refs=count_refs(dto, daemon_dir),
                cli_refs=count_refs(dto, cli_dir),
                test_refs=count_refs(dto, tests_dir),
            )
            summary.entrypoints.append(result)
            summary.by_category['dtos'] += 1

    # 5. api/__init__.py exports
    init_path = api_dir / '__init__.py'
    if init_path.exists():
        init_exports = extract_init_exports(init_path)
        for export in init_exports:
            result = AuditResult(
                name=export,
                category='api_init',
                module='api',
                daemon_refs=count_refs(export, daemon_dir),
                cli_refs=count_refs(export, cli_dir),
                test_refs=count_refs(export, tests_dir),
            )
            summary.entrypoints.append(result)
            summary.by_category['api_init'] += 1

    # Compute totals
    summary.total_entrypoints = len(summary.entrypoints)

    for ep in summary.entrypoints:
        if ep.is_unused:
            summary.unused_count += 1
        elif ep.daemon_refs > 0 and ep.cli_refs > 0:
            summary.both_count += 1
        elif ep.daemon_refs > 0:
            summary.daemon_only_count += 1
        elif ep.cli_refs > 0:
            summary.cli_only_count += 1

    return summary


def print_summary(summary: AuditSummary, verbose: bool = False):
    """Print human-readable summary."""
    print("=" * 60)
    print("API SURFACE AUDIT SUMMARY")
    print("=" * 60)
    print()
    print(f"TOTAL ENTRYPOINTS: {summary.total_entrypoints}")
    print()
    print("BY CATEGORY:")
    for cat, count in sorted(summary.by_category.items()):
        print(f"  {cat:20s}: {count:4d}")
    print()
    print("USAGE COVERAGE:")
    print(f"  Daemon only:       {summary.daemon_only_count:4d}")
    print(f"  CLI only:          {summary.cli_only_count:4d}")
    print(f"  Both daemon+CLI:   {summary.both_count:4d}")
    print(f"  UNUSED (0 refs):   {summary.unused_count:4d}")
    print()

    if verbose:
        print("UNUSED ENTRYPOINTS:")
        for ep in summary.entrypoints:
            if ep.is_unused:
                print(f"  {ep.category:15s} | {ep.name}")
        print()

    # Print JSON for machine parsing
    print("=" * 60)
    print("MACHINE-READABLE JSON:")
    print("=" * 60)
    output = {
        'total_entrypoints': summary.total_entrypoints,
        'by_category': summary.by_category,
        'unused_count': summary.unused_count,
        'daemon_only_count': summary.daemon_only_count,
        'cli_only_count': summary.cli_only_count,
        'both_count': summary.both_count,
    }
    print(json.dumps(output, indent=2))


def main():
    verbose = '-v' in sys.argv or '--verbose' in sys.argv
    summary = run_audit()
    print_summary(summary, verbose=verbose)

    # Return non-zero if there are issues (for CI)
    if summary.unused_count > 0:
        print(f"\nWARNING: {summary.unused_count} unused entrypoints found")


if __name__ == '__main__':
    main()
