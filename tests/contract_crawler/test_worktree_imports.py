"""
Smoke test to verify all recipe modules can be imported in a worktree environment.

This test ensures that:
1. All recipe modules use relative imports (not absolute tests.* imports)
2. Recipe modules can be imported without the main tests package being available
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path


class TestWorktreeImports:
    """Test that recipe modules can be imported in an isolated worktree environment."""

    @pytest.fixture
    def isolated_worktree(self, tmp_path):
        """Create a minimal worktree-like environment with only copied files."""
        repo_root = Path(__file__).parent.parent.parent
        contract_crawler_src = repo_root / "tests" / "contract_crawler"

        # Create worktree structure
        worktree = tmp_path / "worktree"
        tests_dir = worktree / "tests"
        cc_dir = tests_dir / "contract_crawler"
        recipes_dir = cc_dir / "recipes"

        tests_dir.mkdir(parents=True)
        cc_dir.mkdir()
        recipes_dir.mkdir()

        # Create empty __init__.py files
        (tests_dir / "__init__.py").write_text("")
        (cc_dir / "__init__.py").write_text("")

        # Copy only files that generate_golden.py copies
        files_to_copy = [
            "introspection.py",
            "payloads.py",
            "crawler.py",
            "v0_payloads.py",
        ]

        for filename in files_to_copy:
            src = contract_crawler_src / filename
            if src.exists():
                shutil.copy2(src, cc_dir / filename)

        # Copy recipes directory
        src_recipes = contract_crawler_src / "recipes"
        if src_recipes.exists():
            shutil.copytree(src_recipes, recipes_dir, dirs_exist_ok=True)

        return worktree

    def test_recipe_modules_import_in_isolation(self, isolated_worktree):
        """
        Test that all recipe modules can be imported without tests.* package.

        This simulates the worktree environment where only specific files are copied.
        """
        # Temporarily modify sys.path to only include the isolated worktree
        original_path = sys.path.copy()
        original_modules = {k: v for k, v in sys.modules.items()}

        try:
            # Remove any existing tests.contract_crawler from sys.modules
            modules_to_remove = [k for k in sys.modules if k.startswith("tests.contract_crawler")]
            for mod in modules_to_remove:
                del sys.modules[mod]

            # Add only the worktree to path
            sys.path = [str(isolated_worktree / "tests")]

            # Try to import the recipes package
            import importlib

            # Import base module
            spec = importlib.util.spec_from_file_location(
                "contract_crawler",
                isolated_worktree / "tests" / "contract_crawler" / "__init__.py",
                submodule_search_locations=[str(isolated_worktree / "tests" / "contract_crawler")]
            )
            cc_module = importlib.util.module_from_spec(spec)
            sys.modules["contract_crawler"] = cc_module

            # Import v0_payloads
            v0_spec = importlib.util.spec_from_file_location(
                "contract_crawler.v0_payloads",
                isolated_worktree / "tests" / "contract_crawler" / "v0_payloads.py"
            )
            v0_module = importlib.util.module_from_spec(v0_spec)
            sys.modules["contract_crawler.v0_payloads"] = v0_module
            v0_spec.loader.exec_module(v0_module)

            # Import recipes base
            recipes_init = isolated_worktree / "tests" / "contract_crawler" / "recipes" / "__init__.py"
            recipes_spec = importlib.util.spec_from_file_location(
                "contract_crawler.recipes",
                recipes_init,
                submodule_search_locations=[str(isolated_worktree / "tests" / "contract_crawler" / "recipes")]
            )
            recipes_module = importlib.util.module_from_spec(recipes_spec)
            sys.modules["contract_crawler.recipes"] = recipes_module

            # The actual test: can we exec the recipes module?
            # If there are any unguarded absolute imports, this will fail
            try:
                recipes_spec.loader.exec_module(recipes_module)
                assert True, "Recipes module imported successfully"
            except ImportError as e:
                pytest.fail(f"Recipe module import failed: {e}")

        finally:
            # Restore original state
            sys.path = original_path
            # Clear any test modules
            for k in list(sys.modules.keys()):
                if k.startswith("contract_crawler"):
                    del sys.modules[k]
            # Restore original modules (carefully)
            for k, v in original_modules.items():
                if k not in sys.modules:
                    sys.modules[k] = v

    def test_v0_payloads_has_no_absolute_imports(self):
        """Verify v0_payloads.py has no absolute tests.* imports."""
        repo_root = Path(__file__).parent.parent.parent
        v0_payloads_path = repo_root / "tests" / "contract_crawler" / "v0_payloads.py"

        content = v0_payloads_path.read_text()
        assert "from tests." not in content, "v0_payloads.py should not have absolute imports"
        assert "import tests." not in content, "v0_payloads.py should not have absolute imports"

    def test_recipe_files_use_relative_imports_for_v0_payloads(self):
        """Verify all recipe files use relative imports for v0_payloads."""
        repo_root = Path(__file__).parent.parent.parent
        recipes_dir = repo_root / "tests" / "contract_crawler" / "recipes"

        for recipe_file in recipes_dir.glob("*.py"):
            content = recipe_file.read_text()
            if "v0_payloads" in content:
                assert "from ..v0_payloads" in content or "from tests.contract_crawler.v0_payloads" not in content, \
                    f"{recipe_file.name} should use relative import for v0_payloads"
