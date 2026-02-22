#!/usr/bin/env python3
"""
Pretty-print QE parameter JSON in a structural, readable way.

This script reads qe_module_parameters.json and prints it in a hierarchical
structure that's easy to read and understand.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict


def print_param(param: Dict[str, Any], indent: str = "  ") -> None:
    """Print a single parameter with its metadata in markdown format."""
    print(f"{indent}- **name**: `{param.get('name', 'N/A')}`")
    if param.get('type'):
        print(f"{indent}- **type**: `{param.get('type')}`")
    if param.get('default') is not None:
        print(f"{indent}- **default**: `{param.get('default')}`")
    if param.get('enum'):
        enum_vals = param.get('enum', [])
        if len(enum_vals) <= 5:
            print(f"{indent}- **enum**: {', '.join(f'`{v}`' for v in enum_vals)}")
        else:
            print(f"{indent}- **enum**: {len(enum_vals)} values (first 5: {', '.join(f'`{v}`' for v in enum_vals[:5])}...)")
    if param.get('indexing'):
        idx = param['indexing']
        print(f"{indent}- **indexing**:")
        print(f"{indent}  - kind: `{idx.get('kind')}`")
        print(f"{indent}  - index_name: `{idx.get('index_name')}`")
        print(f"{indent}  - start: `{idx.get('start')}`")
        print(f"{indent}  - end: `{idx.get('end')}`")
        print(f"{indent}  - keyword_pattern: `{idx.get('keyword_pattern')}`")
    if param.get('description'):
        desc = param.get('description', '')
        if len(desc) > 200:
            desc = desc[:200] + "..."
        print(f"{indent}- **description**: {desc}")


def print_section(section_name: str, params: Dict[str, Dict[str, Any]], indent: str = "") -> None:
    """Print a section with all its parameters in markdown format."""
    print(f"{indent}#### Section: `{section_name}`")
    print(f"{indent}**Parameters**: {len(params)}")
    print()
    
    # Group parameters by type (with/without indexing)
    # Preserve order from JSON
    with_indexing = []
    without_indexing = []
    
    for key, param in params.items():
        if 'indexing' in param:
            with_indexing.append((key, param))
        else:
            without_indexing.append((key, param))
    
    if with_indexing:
        print(f"{indent}**Array parameters (with indexing)**: {len(with_indexing)}")
        print()
        for key, param in with_indexing[:10]:  # Show first 10
            param_name = key.split('.', 1)[-1] if '.' in key else key
            idx = param.get('indexing', {})
            idx_kind = idx.get('kind', 'unknown')
            idx_end = idx.get('end', '?')
            print(f"{indent}- `{param_name}` ({idx_kind}, end={idx_end})")
        if len(with_indexing) > 10:
            print(f"{indent}- ... and {len(with_indexing) - 10} more")
        print()
    
    if without_indexing:
        print(f"{indent}**Regular parameters**: {len(without_indexing)}")
        print()
        # Show first 10 regular parameters
        for key, param in without_indexing[:10]:
            param_name = key.split('.', 1)[-1] if '.' in key else key
            print(f"{indent}- `{param_name}`")
        if len(without_indexing) > 10:
            print(f"{indent}- ... and {len(without_indexing) - 10} more")
        print()
    
    # Show detailed info for a few key parameters (preserve order)
    print(f"{indent}**Sample parameters (detailed)**:")
    print()
    sample_count = 0
    for key, param in params.items():
        if sample_count >= 3:
            break
        param_name = key.split('.', 1)[-1] if '.' in key else key
        print(f"{indent}##### `{param_name}`")
        print()
        print_param(param, indent)
        print()
        sample_count += 1


def main() -> int:
    repo_root = Path(__file__).parent.parent
    json_path = repo_root / "src" / "qmatsuite" / "data" / "qe_module_parameters.json"
    
    if not json_path.exists():
        sys.stderr.write(f"Error: JSON file not found: {json_path}\n")
        return 1
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print("# QE Module Parameters JSON - Structural View")
    print()
    print(f"- **Schema version**: {data.get('schema_version')}")
    print(f"- **Generated at**: {data.get('generated_at')}")
    print(f"- **Doc pattern**: `{data.get('doc_pattern')}`")
    print()
    
    modules = data.get("modules", {})
    print(f"- **Total modules**: {len(modules)}")
    print()
    
    total_params = 0
    total_with_indexing = 0
    bounded_count = 0
    unbounded_count = 0
    
    # Preserve order from JSON (don't sort)
    for module_name in modules.keys():
        module_data = modules[module_name]
        params = module_data.get("parameters", {})
        total_params += len(params)
        
        # Count indexing
        for param in params.values():
            if 'indexing' in param:
                total_with_indexing += 1
                idx = param.get('indexing', {})
                if idx.get('kind') == 'bounded':
                    bounded_count += 1
                elif idx.get('kind') == 'unbounded':
                    unbounded_count += 1
        
        print()
        print("---")
        print()
        print(f"## Module: {module_name.upper()}")
        print()
        print(f"- **Doc URL**: {module_data.get('doc_url', 'N/A')}")
        print(f"- **Total parameters**: {len(params)}")
        print()
        
        # Group parameters by section (namelist)
        sections: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for key, param in params.items():
            namelist = param.get("namelist", "")
            if not namelist:
                namelist = "UNKNOWN"
            sections.setdefault(namelist, {})[key] = param
        
        print(f"- **Sections**: {len(sections)}")
        print()
        
        # Print each section (preserve order from JSON)
        # Note: dict iteration order is preserved in Python 3.7+
        for section_name in sections.keys():
            section_params = sections[section_name]
            print_section(section_name, section_params, indent="")
            print()
        
        # Show card metadata if present (preserve order)
        if "card_metadata" in module_data:
            card_meta = module_data["card_metadata"]
            print(f"**Card metadata**: {len(card_meta)} cards")
            print()
            for card_name, card_info in card_meta.items():
                print(f"- `{card_name}`: {card_info.get('type', 'N/A')}")
                if card_info.get('default'):
                    print(f"  - Default: `{card_info.get('default')}`")
                if card_info.get('enum'):
                    enum_vals = card_info.get('enum', [])
                    if len(enum_vals) <= 5:
                        print(f"  - Options: {', '.join(f'`{v}`' for v in enum_vals)}")
                    else:
                        print(f"  - Options: {len(enum_vals)} values")
            print()
    
    print()
    print("---")
    print()
    print("## Summary")
    print()
    print(f"- **Total parameters across all modules**: {total_params}")
    print(f"- **Parameters with indexing metadata**: {total_with_indexing}")
    print(f"  - Bounded arrays: {bounded_count}")
    print(f"  - Unbounded arrays: {unbounded_count}")
    print(f"- **Parameters without indexing**: {total_params - total_with_indexing}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
