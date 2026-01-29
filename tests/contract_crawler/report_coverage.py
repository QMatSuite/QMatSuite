"""
Generate coverage matrix report for all RPC methods.

This script analyzes:
- All introspected RPC methods
- Existing golden fixtures
- GUI-used methods (from scanner output)
- Exempt methods

Outputs a machine-readable JSON report.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.contract_crawler.introspection import get_all_rpc_methods
from tests.contract_crawler.recipes import ALL_RECIPES, get_all_recipe_covered_methods
from tests.contract_crawler.test_coverage import EXEMPT_METHODS


GOLDEN_DIR = Path(__file__).parent.parent / "fixtures" / "golden_0873ebf" / "daemon"
GUI_METHODS_FILE = Path(__file__).parent.parent.parent / "gui" / "tests" / "e2e" / "tools" / "gui_rpc_methods.json"
OUTPUT_FILE = Path(__file__).parent / "coverage_report.json"


def load_gui_methods() -> set[str]:
    """Load GUI-used methods from scanner output."""
    if not GUI_METHODS_FILE.exists():
        return set()
    
    try:
        with open(GUI_METHODS_FILE) as f:
            data = json.load(f)
            return set(data.get("methods", []))
    except (json.JSONDecodeError, KeyError):
        return set()


def load_golden_fixtures() -> dict[str, dict[str, Any]]:
    """Load all golden fixtures and extract metadata."""
    fixtures = {}
    
    if not GOLDEN_DIR.exists():
        return fixtures
    
    for fixture_file in GOLDEN_DIR.glob("*.json"):
        if fixture_file.name == "_manifest.json":
            continue
        
        try:
            with open(fixture_file) as f:
                data = json.load(f)
                method_name = fixture_file.stem
                fixtures[method_name] = {
                    "source": data.get("source"),
                    "success": data.get("success", False),
                    "baseline_commit": data.get("baseline_commit"),
                }
        except (json.JSONDecodeError, KeyError):
            continue
    
    return fixtures


def get_recipe_methods() -> set[str]:
    """Get set of methods covered by recipes."""
    return get_all_recipe_covered_methods()


def generate_coverage_report() -> dict[str, Any]:
    """Generate complete coverage matrix report."""
    all_methods = get_all_rpc_methods()
    golden_fixtures = load_golden_fixtures()
    gui_methods = load_gui_methods()
    recipe_methods = get_recipe_methods()
    exempt_methods = set(EXEMPT_METHODS.keys())
    
    # Build method matrix
    method_matrix = []
    gui_missing_methods = []
    
    for method_info in all_methods:
        method_name = method_info.name
        is_gui_used = method_name in gui_methods
        
        # Determine coverage status
        if method_name in exempt_methods:
            coverage_status = "exempt"
            fixture_path = None
            source = None
            exempt_reason = EXEMPT_METHODS[method_name]
        elif method_name in golden_fixtures:
            fixture_data = golden_fixtures[method_name]
            source = fixture_data.get("source")
            if source == "auto_crawler":
                coverage_status = "covered_auto"
            elif source == "recipe":
                coverage_status = "covered_recipe"
            else:
                coverage_status = "covered_unknown"
            fixture_path = str(GOLDEN_DIR / f"{method_name}.json")
            exempt_reason = None
        elif method_name in recipe_methods:
            # Recipe exists but no golden fixture yet
            coverage_status = "covered_recipe"
            fixture_path = None
            source = "recipe"
            exempt_reason = None
        else:
            coverage_status = "not_covered"
            fixture_path = None
            source = None
            exempt_reason = None
        
        method_matrix.append({
            "method_name": method_name,
            "is_gui_used": is_gui_used,
            "coverage_status": coverage_status,
            "fixture_path": fixture_path,
            "source": source,
            "exempt_reason": exempt_reason,
        })
        
        # Track GUI methods that are missing coverage
        if is_gui_used and coverage_status == "not_covered" and method_name not in exempt_methods:
            gui_missing_methods.append(method_name)
    
    # Calculate summary
    total = len(method_matrix)
    covered_auto = sum(1 for m in method_matrix if m["coverage_status"] == "covered_auto")
    covered_recipe = sum(1 for m in method_matrix if m["coverage_status"] == "covered_recipe")
    not_covered = sum(1 for m in method_matrix if m["coverage_status"] == "not_covered")
    exempt = sum(1 for m in method_matrix if m["coverage_status"] == "exempt")
    gui_total = sum(1 for m in method_matrix if m["is_gui_used"])
    gui_covered = sum(1 for m in method_matrix if m["is_gui_used"] and m["coverage_status"].startswith("covered"))
    gui_exempt = sum(1 for m in method_matrix if m["is_gui_used"] and m["coverage_status"] == "exempt")
    
    return {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_methods": total,
            "covered_auto": covered_auto,
            "covered_recipe": covered_recipe,
            "not_covered": not_covered,
            "exempt": exempt,
            "gui_total": gui_total,
            "gui_covered": gui_covered,
            "gui_exempt": gui_exempt,
            "gui_missing_count": len(gui_missing_methods),
        },
        "gui_missing_methods": sorted(gui_missing_methods),
        "methods": method_matrix,
    }


def main():
    """Generate and write coverage report."""
    report = generate_coverage_report()
    
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"Coverage report written to: {OUTPUT_FILE}")
    print(f"\nSummary:")
    print(f"  Total methods: {report['summary']['total_methods']}")
    print(f"  Covered (auto): {report['summary']['covered_auto']}")
    print(f"  Covered (recipe): {report['summary']['covered_recipe']}")
    print(f"  Not covered: {report['summary']['not_covered']}")
    print(f"  Exempt: {report['summary']['exempt']}")
    print(f"  GUI methods: {report['summary']['gui_total']}")
    print(f"  GUI covered: {report['summary']['gui_covered']}")
    print(f"  GUI missing: {report['summary']['gui_missing_count']}")
    if report['gui_missing_methods']:
        print(f"\nGUI missing methods ({len(report['gui_missing_methods'])}):")
        for method in report['gui_missing_methods'][:10]:
            print(f"  - {method}")
        if len(report['gui_missing_methods']) > 10:
            print(f"  ... and {len(report['gui_missing_methods']) - 10} more")


if __name__ == "__main__":
    main()

