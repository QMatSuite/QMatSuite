#!/usr/bin/env python3
"""
Generate a diff report comparing v1, v2, and v3 QE parameter JSON files.

Output: docs/QE_PARAMETER_JSON_DIFF_REPORT.md
"""

import json
from pathlib import Path
from typing import Dict, Set, Any, List


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file, return empty dict if not found."""
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def get_parameter_keys(module_data: Dict[str, Any]) -> Set[str]:
    """Extract all parameter keys from a module's data."""
    params = module_data.get("parameters", {})
    return set(params.keys())


def generate_diff_report() -> str:
    """Generate markdown diff report."""
    data_dir = Path(__file__).parent.parent / "src" / "quantumvitas" / "data"
    
    v0_path = data_dir / "qe_module_parameters.legacy.v0.json"
    v1_path = data_dir / "qe_module_parameters.legacy.v1.json"
    v2_path = data_dir / "qe_module_parameters.legacy.v2.json"
    v3_path = data_dir / "qe_module_parameters.json"
    
    v0_data = load_json(v0_path) if v0_path.exists() else None
    v1_data = load_json(v1_path) if v1_path.exists() else None
    v2_data = load_json(v2_path) if v2_path.exists() else None
    v3_data = load_json(v3_path)
    
    lines = []
    lines.append("# QE Parameter JSON Diff Report")
    lines.append("")
    lines.append("This report compares parameter metadata across JSON schema versions:")
    if v0_data:
        lines.append("- **v0** (legacy): `qe_module_parameters.legacy.v0.json`")
    if v1_data:
        lines.append("- **v1** (legacy): `qe_module_parameters.legacy.v1.json`")
    if v2_data:
        lines.append("- **v2** (legacy): `qe_module_parameters.legacy.v2.json`")
    lines.append("- **v3** (current): `qe_module_parameters.json`")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Get all modules
    all_modules = set()
    if v0_data:
        all_modules.update(v0_data.get("modules", {}).keys())
    if v1_data:
        all_modules.update(v1_data.get("modules", {}).keys())
    if v2_data:
        all_modules.update(v2_data.get("modules", {}).keys())
    if v3_data:
        all_modules.update(v3_data.get("modules", {}).keys())
    
    all_modules = sorted(all_modules)
    
    # Per-module table
    lines.append("## Per-Module Parameter Counts")
    lines.append("")
    if v0_data:
        lines.append("| Module | v0 | v1 | v2 | v3 | v1-v0 | v2-v1 | v3-v2 |")
        lines.append("|--------|----|----|----|----|-------|-------|-------|")
    else:
        lines.append("| Module | v1 | v2 | v3 | v1-v0 | v2-v1 | v3-v2 |")
        lines.append("|--------|----|----|----|-------|-------|-------|")
    
    global_v0_total = 0
    global_v1_total = 0
    global_v2_total = 0
    global_v3_total = 0
    global_v1_added = 0
    global_v1_removed = 0
    global_v2_added = 0
    global_v2_removed = 0
    global_v3_added = 0
    global_v3_removed = 0
    
    module_diffs: List[Dict[str, Any]] = []
    
    for module in all_modules:
        v0_mod = v0_data.get("modules", {}).get(module, {}) if v0_data else {}
        v1_mod = v1_data.get("modules", {}).get(module, {}) if v1_data else {}
        v2_mod = v2_data.get("modules", {}).get(module, {}) if v2_data else {}
        v3_mod = v3_data.get("modules", {}).get(module, {}) if v3_data else {}
        
        v0_keys = get_parameter_keys(v0_mod) if v0_data else set()
        v1_keys = get_parameter_keys(v1_mod) if v1_data else set()
        v2_keys = get_parameter_keys(v2_mod) if v2_data else set()
        v3_keys = get_parameter_keys(v3_mod) if v3_data else set()
        
        v0_count = len(v0_keys) if v0_data else 0
        v1_count = len(v1_keys) if v1_data else 0
        v2_count = len(v2_keys) if v2_data else 0
        v3_count = len(v3_keys) if v3_data else 0
        
        v2_added = len(v2_keys - v1_keys)
        v2_removed = len(v1_keys - v2_keys)
        v3_added = len(v3_keys - v2_keys)
        v3_removed = len(v2_keys - v3_keys)
        
        global_v1_total += v1_count
        global_v2_total += v2_count
        global_v3_total += v3_count
        global_v2_added += v2_added
        global_v2_removed += v2_removed
        global_v3_added += v3_added
        global_v3_removed += v3_removed
        
        v2_diff_str = f"+{v2_added}" if v2_added > 0 else ""
        if v2_removed > 0:
            v2_diff_str += f" / -{v2_removed}" if v2_diff_str else f"-{v2_removed}"
        v2_diff_str = v2_diff_str or "—"
        
        v3_diff_str = f"+{v3_added}" if v3_added > 0 else ""
        if v3_removed > 0:
            v3_diff_str += f" / -{v3_removed}" if v3_diff_str else f"-{v3_removed}"
        v3_diff_str = v3_diff_str or "—"
        
        lines.append(f"| {module} | {v1_count} | {v2_count} | {v3_count} | {v2_diff_str} | {v3_diff_str} |")
        
        # Store diff details for later
        if v2_added > 0 or v2_removed > 0 or v3_added > 0 or v3_removed > 0:
            module_diffs.append({
                "module": module,
                "v2_added": sorted(v2_keys - v1_keys),
                "v2_removed": sorted(v1_keys - v2_keys),
                "v3_added": sorted(v3_keys - v2_keys),
                "v3_removed": sorted(v2_keys - v3_keys),
            })
    
    lines.append("")
    lines.append("### Global Totals")
    lines.append("")
    lines.append(f"- **v1 total**: {global_v1_total} parameters")
    lines.append(f"- **v2 total**: {global_v2_total} parameters (+{global_v2_added}, -{global_v2_removed} vs v1)")
    lines.append(f"- **v3 total**: {global_v3_total} parameters (+{global_v3_added}, -{global_v3_removed} vs v2)")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Detailed diffs for modules with changes
    if module_diffs:
        lines.append("## Detailed Parameter Changes")
        lines.append("")
        
        for diff in module_diffs:
            module = diff["module"]
            lines.append(f"### Module: `{module}`")
            lines.append("")
            
            if diff["v2_added"]:
                lines.append(f"#### v2-v1: Added ({len(diff['v2_added'])} parameters)")
                lines.append("")
                for key in diff["v2_added"][:50]:  # Limit to 50
                    lines.append(f"- `{key}`")
                if len(diff["v2_added"]) > 50:
                    lines.append(f"- ... and {len(diff['v2_added']) - 50} more")
                lines.append("")
            
            if diff["v2_removed"]:
                lines.append(f"#### v2-v1: Removed ({len(diff['v2_removed'])} parameters)")
                lines.append("")
                for key in diff["v2_removed"][:50]:  # Limit to 50
                    lines.append(f"- `{key}`")
                if len(diff["v2_removed"]) > 50:
                    lines.append(f"- ... and {len(diff['v2_removed']) - 50} more")
                lines.append("")
            
            if diff["v3_added"]:
                lines.append(f"#### v3-v2: Added ({len(diff['v3_added'])} parameters)")
                lines.append("")
                for key in diff["v3_added"][:50]:  # Limit to 50
                    lines.append(f"- `{key}`")
                if len(diff["v3_added"]) > 50:
                    lines.append(f"- ... and {len(diff['v3_added']) - 50} more")
                lines.append("")
            
            if diff["v3_removed"]:
                lines.append(f"#### v3-v2: Removed ({len(diff['v3_removed'])} parameters)")
                lines.append("")
                for key in diff["v3_removed"][:50]:  # Limit to 50
                    lines.append(f"- `{key}`")
                if len(diff["v3_removed"]) > 50:
                    lines.append(f"- ... and {len(diff['v3_removed']) - 50} more")
                lines.append("")
            
            lines.append("---")
            lines.append("")
    
    # v3-specific improvements summary
    if v3_data:
        lines.append("## v3 Schema Improvements")
        lines.append("")
        lines.append("v3 introduces the following improvements over v2:")
        lines.append("")
        lines.append("### A) Better Default/Status/See Parsing")
        lines.append("")
        lines.append("- Parses `Default:`, `Status:`, and `See:` rows by reading left cell text, not row index")
        lines.append("- Fixes cases where `See:` row appears before `Default:` (e.g., `celldm` parameter)")
        lines.append("- Correctly identifies `Status: REQUIRED` for parameters like `ibrav`")
        lines.append("")
        
        lines.append("### B) Better Enum Extraction")
        lines.append("")
        lines.append("- Prioritizes `<span class=\"flag\">` elements (e.g., PH `verbosity` parameter)")
        lines.append("- Falls back to `<dl><dt><tt>` structures")
        lines.append("- Preserves quotes in enum values (e.g., `'debug'`, `'high'`)")
        lines.append("")
        
        lines.append("### C) Improved Indexing Support")
        lines.append("")
        lines.append("- Enhanced detection of array parameters like `celldm(i), i=1,6`")
        lines.append("- Better handling of unbounded arrays like `alpha_mix(niter)`")
        lines.append("- Consistent `keyword_pattern` format: `{base}({{index}})`")
        lines.append("")
        
        lines.append("### D) Better Description Rendering")
        lines.append("")
        lines.append("- Handles `<pre>` blocks with proper dedenting and blank line compression")
        lines.append("- Renders `<dl>` definition lists as readable bullet lists")
        lines.append("- Preserves structure while removing excessive whitespace")
        lines.append("- Ensures max 2 consecutive blank lines")
        lines.append("")
        
        lines.append("### E) Schema Version 3")
        lines.append("")
        lines.append("- Adds optional `status` field (e.g., `REQUIRED`, `OPTIONAL`)")
        lines.append("- Adds optional `see_also` field (list of related parameter names)")
        lines.append("- Maintains backward compatibility with v2 structure")
        lines.append("")
    
    return "\n".join(lines)


def main() -> int:
    """Generate and write diff report."""
    report_path = Path(__file__).parent.parent / "docs" / "QE_PARAMETER_JSON_DIFF_REPORT.md"
    
    report_content = generate_diff_report()
    
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_content, encoding="utf-8")
    
    print(f"Diff report written to: {report_path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
