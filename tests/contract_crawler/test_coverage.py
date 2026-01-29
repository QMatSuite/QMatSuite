"""Enforce method coverage policy based on actual crawl success."""

import pytest
from pathlib import Path

from tests.contract_crawler.introspection import get_all_rpc_methods
from tests.contract_crawler.crawler import crawl_all_methods, CrawlReport
from tests.contract_crawler.recipes import ALL_RECIPES


# Exempt methods with mandatory reasons
EXEMPT_METHODS: dict[str, str] = {
    "shutdown": "Terminates daemon process; tested manually",
    "compile_fixture_volume": "Dev-only endpoint requiring specific fixture files",
    "download_sssp_library": "Network-dependent; tested in integration suite",
    "download_all_sssp": "Network-dependent; tested in integration suite",
    "structure_search_online": "Network-dependent; tested in integration suite",
    "structure_get_online_candidate": "Network-dependent; tested in integration suite",
    "structure_import_online_candidate": "Network-dependent; tested in integration suite",
    "search_legacy_pseudos": "Network-dependent; tested in integration suite",
    "download_pseudo_by_filename": "Network-dependent; tested in integration suite",
    "download_pseudo_candidate": "Network-dependent; tested in integration suite",
}


def test_exempt_methods_are_valid():
    """
    Verify EXEMPT_METHODS structure and integrity.

    Requirements:
    - Every exempt method must exist in daemon handler registry
    - Every exempt method must have a non-empty reason string
    - Total exempt count capped at 15 to prevent exemption creep
    """
    all_methods = {m.name for m in get_all_rpc_methods()}

    # Check all exempt methods exist
    unknown_exempt = set(EXEMPT_METHODS.keys()) - all_methods
    assert not unknown_exempt, f"EXEMPT contains unknown methods: {unknown_exempt}"

    # Check all reasons are non-empty
    empty_reasons = [m for m, reason in EXEMPT_METHODS.items() if not reason or not reason.strip()]
    assert not empty_reasons, f"EXEMPT methods with empty reasons: {empty_reasons}"

    # Check exemption count cap
    assert len(EXEMPT_METHODS) <= 15, (
        f"EXEMPT list has {len(EXEMPT_METHODS)} entries (max 15). "
        f"Review exemptions to prevent coverage erosion."
    )

    print(f"\nExempt methods validated: {len(EXEMPT_METHODS)} methods with reasons")


def test_auto_crawl_methods_actually_succeed():
    """
    Verify that methods we expect to auto-crawl ACTUALLY succeed when crawled.

    This test runs the actual crawler and checks success, rather than
    using set subtraction to assume coverage.
    """
    report = crawl_all_methods()

    # Methods that failed (not just marked as needing recipes)
    actual_failures = [
        r for r in report.results
        if not r.success and not r.needs_recipe and r.method_name not in EXEMPT_METHODS
    ]

    if actual_failures:
        failure_details = "\n".join([
            f"  - {r.method_name}: {r.error or r.skipped_reason}"
            for r in actual_failures
        ])
        pytest.fail(
            f"Methods expected to auto-crawl but ACTUALLY FAILED:\n{failure_details}\n\n"
            f"Fix the method or add it to needs_recipes() if it requires setup."
        )

    # Report coverage stats
    covered_count = len(report.covered)
    total_count = report.total
    print(f"\nAuto-crawl coverage: {covered_count}/{total_count} methods succeeded")


def test_recipes_actually_succeed(tmp_path: Path):
    """
    Verify that recipe-covered methods ACTUALLY succeed when executed.

    This test runs each recipe and checks success, rather than
    just checking if a recipe exists for the method.
    """
    failures = []

    for recipe_cls in ALL_RECIPES:
        recipe_dir = tmp_path / recipe_cls.__name__
        recipe_dir.mkdir(exist_ok=True)

        recipe = recipe_cls(recipe_dir)
        result = recipe.execute()

        if not result.success:
            failures.append(f"{recipe_cls.__name__} ({recipe.method_name}): {result.error}")

    if failures:
        pytest.fail(
            f"Recipes that ACTUALLY FAILED:\n" +
            "\n".join(f"  - {f}" for f in failures) +
            "\n\nFix the recipe or the underlying handler."
        )

    print(f"\nRecipe coverage: {len(ALL_RECIPES)} methods succeeded via recipes")


def test_all_methods_covered_or_exempt():
    """
    Every public RPC method must be:
    1. ACTUALLY covered by auto-crawler (verified by success), OR
    2. ACTUALLY covered by a recipe (verified by success), OR
    3. Explicitly exempt with documented reason

    This is the final gate - it combines auto-crawl and recipe results.
    """
    # Get all registered methods
    all_methods = {m.name for m in get_all_rpc_methods()}

    # Run actual crawler to get real successes
    report = crawl_all_methods()
    auto_crawl_succeeded = {r.method_name for r in report.covered}

    # Get recipe-covered methods
    recipe_covered = {r.method_name for r in ALL_RECIPES}

    # Calculate actual coverage
    exempt_methods_set = set(EXEMPT_METHODS.keys())
    actually_covered = auto_crawl_succeeded | recipe_covered | exempt_methods_set
    uncovered = all_methods - actually_covered

    # Check all methods are covered
    if uncovered:
        pytest.fail(
            f"Methods with NO ACTUAL COVERAGE:\n" +
            "\n".join(f"  - {m}" for m in sorted(uncovered)) +
            "\n\nEach method must either:\n"
            "  1. Succeed in auto-crawl (add minimal payload to payloads.py)\n"
            "  2. Have a working recipe (add to recipes/)\n"
            "  3. Be explicitly exempt (add to EXEMPT_METHODS with reason)"
        )

    # Print coverage summary
    print(f"\nCoverage summary:")
    print(f"  Auto-crawl succeeded: {len(auto_crawl_succeeded)}")
    print(f"  Recipe covered: {len(recipe_covered)}")
    print(f"  Exempt: {len(EXEMPT_METHODS)}")
    print(f"  Total methods: {len(all_methods)}")
    print(f"  Coverage: {len(actually_covered)}/{len(all_methods)} ({len(actually_covered)*100//len(all_methods)}%)")

