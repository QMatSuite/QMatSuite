"""
AST-based import scanner for architecture gate tests.

This module provides AST-based detection of forbidden imports.
It does NOT use regex/grep, which misses function-local imports and multiline imports.
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set


@dataclass
class Violation:
    """Represents a forbidden import violation."""

    file_path: Path
    line_number: int
    module_name: str
    forbidden_prefix: str
    import_type: str  # "import" or "from"


class ImportScanner:
    """
    AST-based scanner for forbidden imports.

    Detects imports that match forbidden prefixes using Python AST parsing.
    This is more accurate than regex/grep because it:
    - Handles multiline imports
    - Detects function-local imports
    - Properly parses complex import statements
    """

    def __init__(
        self,
        forbidden_prefixes: tuple[str, ...],
        allowed_paths: Optional[dict[str, Set[str]]] = None,
    ):
        """
        Initialize the scanner.

        Args:
            forbidden_prefixes: Tuple of module prefixes that are forbidden
                (e.g., ("qmatsuite.core", "qmatsuite.calculation"))
            allowed_paths: Optional dict mapping file paths (as strings) to sets
                of allowed module prefixes. Used for bootstrap exceptions.
                Example: {"src/qmatsuite/frontends/_shared/bootstrap.py": {"qmatsuite.core.context"}}
        """
        self.forbidden_prefixes = forbidden_prefixes
        self.allowed_paths = allowed_paths or {}

    def _is_forbidden(self, module_name: str, file_path: Path) -> bool:
        """
        Check if a module name is forbidden.

        Args:
            module_name: The imported module name (e.g., "qmatsuite.core.resolution")
            file_path: The file path where the import occurs

        Returns:
            True if the import is forbidden, False otherwise
        """
        # Check if this file has an allowlist
        file_path_str = str(file_path)
        if file_path_str in self.allowed_paths:
            allowed = self.allowed_paths[file_path_str]
            # If the module matches an allowed prefix, it's not forbidden
            if any(module_name.startswith(prefix) for prefix in allowed):
                return False

        # Check if module matches any forbidden prefix
        return any(module_name.startswith(prefix) for prefix in self.forbidden_prefixes)

    def _check_import_node(self, node: ast.Import, file_path: Path) -> List[Violation]:
        """Check an ast.Import node for violations."""
        violations = []
        for alias in node.names:
            module_name = alias.name
            if self._is_forbidden(module_name, file_path):
                violations.append(
                    Violation(
                        file_path=file_path,
                        line_number=node.lineno,
                        module_name=module_name,
                        forbidden_prefix=next(
                            p for p in self.forbidden_prefixes if module_name.startswith(p)
                        ),
                        import_type="import",
                    )
                )
        return violations

    def _check_importfrom_node(
        self, node: ast.ImportFrom, file_path: Path
    ) -> List[Violation]:
        """Check an ast.ImportFrom node for violations."""
        violations = []
        if node.module is None:
            # Relative import like "from . import something"
            return violations

        module_name = node.module
        if self._is_forbidden(module_name, file_path):
            violations.append(
                Violation(
                    file_path=file_path,
                    line_number=node.lineno,
                    module_name=module_name,
                    forbidden_prefix=next(
                        p for p in self.forbidden_prefixes if module_name.startswith(p)
                    ),
                    import_type="from",
                )
            )
        return violations

    def scan_file(self, file_path: Path) -> List[Violation]:
        """
        Scan a single Python file for forbidden imports.

        Args:
            file_path: Path to the Python file to scan

        Returns:
            List of Violation objects found in the file
        """
        violations = []
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            # Skip files with syntax errors (they'll be caught by other tests)
            return violations
        except Exception:
            # Skip files that can't be read/parsed
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                violations.extend(self._check_import_node(node, file_path))
            elif isinstance(node, ast.ImportFrom):
                violations.extend(self._check_importfrom_node(node, file_path))

        return violations

    def scan_directory(self, root_dir: Path) -> List[Violation]:
        """
        Scan all Python files in a directory recursively.

        Args:
            root_dir: Root directory to scan

        Returns:
            List of all Violation objects found
        """
        violations = []
        if not root_dir.exists():
            return violations

        for py_file in root_dir.rglob("*.py"):
            violations.extend(self.scan_file(py_file))

        return violations


def scan_python_files(
    root_dirs: List[Path],
    forbidden_prefixes: tuple[str, ...],
    allowed_paths: Optional[dict[str, Set[str]]] = None,
) -> List[Violation]:
    """
    Scan multiple directories for forbidden imports.

    Args:
        root_dirs: List of directories to scan
        forbidden_prefixes: Tuple of forbidden module prefixes
        allowed_paths: Optional dict of file paths to allowed prefixes (for bootstrap)

    Returns:
        List of all Violation objects found
    """
    scanner = ImportScanner(forbidden_prefixes, allowed_paths)
    all_violations = []
    for root_dir in root_dirs:
        all_violations.extend(scanner.scan_directory(root_dir))
    return all_violations

