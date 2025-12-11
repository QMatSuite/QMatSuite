#!/usr/bin/env python3
"""
Generate validation report data comparing v2 schema against legacy v1 snapshot.

This script analyzes both JSON files and generates statistics for:
- Parameter coverage (v1 vs v2)
- Module-by-module comparison
- Metadata completeness
- Missing/extra parameters

Usage:
    python tools/generate_qe_parameter_validation_report.py [--output OUTPUT]

Output is printed to stdout in a structured format that can be used to update
docs/QE_PARAMETER_VALIDATION_REPORT.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_v1_parameters(v1_data: Dict[str, Any]) -> Dict[str, Set[Tuple[str, str]]]:
    """
    Extract parameters from v1 schema.
    
    Returns:
        Dict mapping module_name -> set of (section, param_name) tuples
    """
    result: Dict[str, Set[Tuple[str, str]]] = {}
    for module_name, module_data in v1_data.get("modules", {}).items():
        params = set()
        for section, param_list in module_data.get("sections", {}).items():
            # Keep section names as-is: & prefix indicates namelist, no & indicates card section
            # Do NOT normalize by adding & arbitrarily - the prefix is meaningful
            for param_name in param_list:
                params.add((section, param_name))
        result[module_name] = params
    return result


def extract_v2_parameters(v2_data: Dict[str, Any]) -> Dict[str, Set[Tuple[str, str]]]:
    """
    Extract parameters from v2 schema.
    
    Returns:
        Dict mapping module_name -> set of (section, param_name) tuples
    """
    result: Dict[str, Set[Tuple[str, str]]] = {}
    for module_name, module_data in v2_data.get("modules", {}).items():
        params = set()
        for key, param_data in module_data.get("parameters", {}).items():
            section = param_data.get("namelist")
            name = param_data.get("name")
            if section and name:
                params.add((section, name))
        result[module_name] = params
    return result


def analyze_metadata_completeness(v2_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze metadata completeness for v2 parameters.
    
    Returns:
        Dict with statistics about type, default, enum, description coverage
    """
    total = 0
    with_type = 0
    with_default = 0
    with_enum = 0
    with_desc = 0
    namelist_params = 0
    card_params = 0
    
    namelist_with_type = 0
    namelist_with_default = 0
    namelist_with_enum = 0
    namelist_with_desc = 0
    
    for module_name, module_data in v2_data.get("modules", {}).items():
        for key, param in module_data.get("parameters", {}).items():
            total += 1
            has_type = bool(param.get("type"))
            has_default = bool(param.get("default"))
            has_enum = bool(param.get("enum"))
            has_desc = bool(param.get("description"))
            
            if has_type:
                with_type += 1
                namelist_params += 1
                namelist_with_type += 1
                if has_default:
                    namelist_with_default += 1
                if has_enum:
                    namelist_with_enum += 1
                if has_desc:
                    namelist_with_desc += 1
            else:
                card_params += 1
            
            if has_default:
                with_default += 1
            if has_enum:
                with_enum += 1
            if has_desc:
                with_desc += 1
    
    return {
        "total": total,
        "with_type": with_type,
        "with_default": with_default,
        "with_enum": with_enum,
        "with_desc": with_desc,
        "namelist_params": namelist_params,
        "card_params": card_params,
        "namelist_with_type": namelist_with_type,
        "namelist_with_default": namelist_with_default,
        "namelist_with_enum": namelist_with_enum,
        "namelist_with_desc": namelist_with_desc,
    }


def compare_modules(
    v1_params: Dict[str, Set[Tuple[str, str]]],
    v2_params: Dict[str, Set[Tuple[str, str]]],
) -> Dict[str, Any]:
    """
    Compare parameters module by module.
    
    Returns:
        Dict with comparison statistics per module
    """
    all_modules = set(v1_params.keys()) | set(v2_params.keys())
    comparison = {}
    
    for module in sorted(all_modules):
        v1_set = v1_params.get(module, set())
        v2_set = v2_params.get(module, set())
        
        only_v1 = v1_set - v2_set
        only_v2 = v2_set - v1_set
        common = v1_set & v2_set
        
        v1_count = len(v1_set)
        v2_count = len(v2_set)
        coverage = (v2_count * 100 // v1_count) if v1_count > 0 else 0
        
        comparison[module] = {
            "v1_count": v1_count,
            "v2_count": v2_count,
            "common": len(common),
            "only_v1": len(only_v1),
            "only_v2": len(only_v2),
            "coverage": coverage,
            "only_v1_samples": sorted(list(only_v1))[:10],
            "only_v2_samples": sorted(list(only_v2))[:10],
        }
    
    return comparison


def generate_report(
    v1_path: Path,
    v2_path: Path,
    output_path: Path | None = None,
) -> None:
    """Generate validation report data."""
    # Load data
    v1_data = load_json(v1_path)
    v2_data = load_json(v2_path)
    
    # Extract parameters
    v1_params = extract_v1_parameters(v1_data)
    v2_params = extract_v2_parameters(v2_data)
    
    # Overall statistics
    v1_total = sum(len(params) for params in v1_params.values())
    v2_total = sum(len(params) for params in v2_params.values())
    coverage_pct = (v2_total * 100 // v1_total) if v1_total > 0 else 0
    
    # Module comparison
    module_comparison = compare_modules(v1_params, v2_params)
    
    # Metadata completeness
    metadata_stats = analyze_metadata_completeness(v2_data)
    
    # Generate report
    lines = []
    lines.append("=" * 80)
    lines.append("QE PARAMETER VALIDATION REPORT DATA")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Generated from:")
    lines.append(f"  V1 (legacy): {v1_path}")
    lines.append(f"  V2 (new): {v2_path}")
    lines.append("")
    
    # Overall summary
    lines.append("## OVERALL SUMMARY")
    lines.append("")
    lines.append(f"Total parameters:")
    lines.append(f"  V1 (legacy): {v1_total}")
    lines.append(f"  V2 (new): {v2_total}")
    lines.append(f"  Difference: {v2_total - v1_total:+d}")
    lines.append(f"  Coverage: {coverage_pct}%")
    lines.append("")
    
    # Module-by-module
    lines.append("## MODULE-BY-MODULE COMPARISON")
    lines.append("")
    lines.append("| Module | V1 | V2 | Coverage | Only V1 | Only V2 |")
    lines.append("|--------|----|----|----------|---------|---------|")
    for module, stats in sorted(module_comparison.items()):
        lines.append(
            f"| {module:20s} | {stats['v1_count']:3d} | {stats['v2_count']:3d} | "
            f"{stats['coverage']:3d}% | {stats['only_v1']:3d} | {stats['only_v2']:3d} |"
        )
    lines.append("")
    
    # Detailed differences for key modules
    lines.append("## DETAILED DIFFERENCES (Key Modules)")
    lines.append("")
    for module in ["pw", "cp", "ph", "ld1", "neb"]:
        if module in module_comparison:
            stats = module_comparison[module]
            lines.append(f"### {module.upper()} Module")
            lines.append("")
            lines.append(f"- V1 parameters: {stats['v1_count']}")
            lines.append(f"- V2 parameters: {stats['v2_count']}")
            lines.append(f"- Coverage: {stats['coverage']}%")
            lines.append(f"- Only in V1: {stats['only_v1']} parameters")
            if stats['only_v1_samples']:
                lines.append(f"  - Examples: {', '.join(f'{s}.{p}' for s, p in stats['only_v1_samples'][:5])}")
            lines.append(f"- Only in V2: {stats['only_v2']} parameters")
            if stats['only_v2_samples']:
                lines.append(f"  - Examples: {', '.join(f'{s}.{p}' for s, p in stats['only_v2_samples'][:5])}")
            lines.append("")
    
    # Metadata completeness
    lines.append("## METADATA COMPLETENESS (V2)")
    lines.append("")
    lines.append(f"Total parameters: {metadata_stats['total']}")
    lines.append(f"  - Namelist parameters (with type): {metadata_stats['namelist_params']}")
    lines.append(f"  - Card parameters (no type): {metadata_stats['card_params']}")
    lines.append("")
    lines.append("Overall metadata coverage:")
    lines.append(f"  - Type: {metadata_stats['with_type']}/{metadata_stats['total']} ({metadata_stats['with_type']*100//metadata_stats['total']}%)")
    lines.append(f"  - Default: {metadata_stats['with_default']}/{metadata_stats['total']} ({metadata_stats['with_default']*100//metadata_stats['total']}%)")
    lines.append(f"  - Enum: {metadata_stats['with_enum']}/{metadata_stats['total']} ({metadata_stats['with_enum']*100//metadata_stats['total']}%)")
    lines.append(f"  - Description: {metadata_stats['with_desc']}/{metadata_stats['total']} ({metadata_stats['with_desc']*100//metadata_stats['total']}%)")
    lines.append("")
    lines.append("Namelist parameters metadata (parameters with types):")
    lines.append(f"  - Type: {metadata_stats['namelist_with_type']}/{metadata_stats['namelist_params']} (100%)")
    lines.append(f"  - Default: {metadata_stats['namelist_with_default']}/{metadata_stats['namelist_params']} ({metadata_stats['namelist_with_default']*100//metadata_stats['namelist_params'] if metadata_stats['namelist_params'] > 0 else 0}%)")
    lines.append(f"  - Enum: {metadata_stats['namelist_with_enum']}/{metadata_stats['namelist_params']} ({metadata_stats['namelist_with_enum']*100//metadata_stats['namelist_params'] if metadata_stats['namelist_params'] > 0 else 0}%)")
    lines.append(f"  - Description: {metadata_stats['namelist_with_desc']}/{metadata_stats['namelist_params']} ({metadata_stats['namelist_with_desc']*100//metadata_stats['namelist_params'] if metadata_stats['namelist_params'] > 0 else 0}%)")
    lines.append("")
    
    # Output
    report_text = "\n".join(lines)
    
    if output_path:
        output_path.write_text(report_text, encoding="utf-8")
        print(f"Report written to: {output_path}", file=sys.stderr)
    else:
        print(report_text)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate validation report data comparing v2 schema against legacy v1 snapshot."
    )
    parser.add_argument(
        "--v1-path",
        type=Path,
        default=Path(__file__).parent.parent / "src" / "quantumvitas" / "data" / "qe_module_parameters.legacy.json",
        help="Path to legacy v1 JSON file",
    )
    parser.add_argument(
        "--v2-path",
        type=Path,
        default=Path(__file__).parent.parent / "src" / "quantumvitas" / "data" / "qe_module_parameters.json",
        help="Path to v2 JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args()
    
    if not args.v1_path.exists():
        print(f"Error: V1 file not found: {args.v1_path}", file=sys.stderr)
        return 1
    
    if not args.v2_path.exists():
        print(f"Error: V2 file not found: {args.v2_path}", file=sys.stderr)
        return 1
    
    try:
        generate_report(args.v1_path, args.v2_path, args.output)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
