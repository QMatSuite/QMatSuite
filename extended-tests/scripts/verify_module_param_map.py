#!/usr/bin/env python3
"""
Verify that the generated QE module parameter map covers real test-suite inputs.

This script scans QE test-suite input files, parses them with QEInputParser,
and compares the detected namelist parameters against
`src/quantumvitas/data/qe_module_parameters.json`.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from quantumvitas.data import load_qe_parameter_map
from quantumvitas.io import QEInputParser
from quantumvitas.io.model import QEModule


def iter_input_files(base_paths: Iterable[Path]) -> Iterable[Path]:
    for base in base_paths:
        if base.is_file():
            yield base
            continue
        for path in base.rglob("*.in"):
            if path.is_file():
                yield path


def module_key(module: Optional[QEModule]) -> Optional[str]:
    if module is None:
        return None
    return module.name.lower()


def extract_sections_from_input(input_path: Path) -> Tuple[Optional[str], Dict[str, Set[str]]]:
    try:
        qe_input = QEInputParser.parse_file(input_path)
    except Exception:
        return None, {}

    module = module_key(qe_input.detect_module())
    sections: Dict[str, Set[str]] = {}
    for namelist in qe_input.namelists:
        section_name = f"&{namelist.name.upper()}"
        sections.setdefault(section_name, set()).update(map(str.upper, namelist.parameters.keys()))
    # Cards are usually free-form; for verification we focus on namelists (&...).
    return module, sections


def summarize(results: Dict[str, Dict[str, float]]) -> None:
    print("\nCoverage summary per module:")
    print("module     files  sections  params")
    for module, stats in sorted(results.items()):
        print(
            f"{module:10s} "
            f"{int(stats['files']):5d} "
            f"{stats['section_match']:.1%} "
            f"{stats['param_match']:.1%}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate QE module parameter metadata using QE test-suite inputs."
    )
    parser.add_argument(
        "--testsuite",
        nargs="+",
        default=[Path("extended-tests") / "suites" / "qe_testsuite"],
        type=Path,
        help="Path(s) to QE test-suite directories or specific input files.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of files to inspect.",
    )
    args = parser.parse_args()

    parameter_map = load_qe_parameter_map().get("modules", {})
    stats: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    missing_sections: Dict[str, Set[str]] = defaultdict(set)
    missing_params: Dict[str, Set[str]] = defaultdict(set)
    files_processed = 0

    for input_file in iter_input_files(args.testsuite):
        if args.limit and files_processed >= args.limit:
            break

        module, sections = extract_sections_from_input(input_file)
        if module is None or not sections:
            continue

        files_processed += 1
        stats[module]["files"] += 1

        reference_sections = {k.upper(): set(map(str.upper, v)) for k, v in parameter_map.get(module, {}).get("sections", {}).items()}
        sec_matches = 0
        sec_total = 0
        param_matches = 0
        param_total = 0

        for section_name, params in sections.items():
            sec_total += 1
            reference_params = reference_sections.get(section_name.upper())
            if reference_params is None:
                missing_sections[module].add(section_name)
                continue
            sec_matches += 1

            for param in params:
                param_total += 1
                if param.upper() in reference_params:
                    param_matches += 1
                else:
                    missing_params[module].add(f"{section_name}.{param}")

        if sec_total:
            stats[module]["section_match"] += sec_matches / sec_total
        if param_total:
            stats[module]["param_match"] += param_matches / param_total

    if files_processed == 0:
        print("No input files processed. Check --testsuite path.")
        return 1

    summarize(stats)

    if missing_sections:
        print("\nMissing sections:")
        for module, sections in sorted(missing_sections.items()):
            print(f"  {module}: {', '.join(sorted(sections))}")

    if missing_params:
        print("\nMissing params:")
        for module, params in sorted(missing_params.items()):
            sample = ", ".join(sorted(params)[:10])
            print(f"  {module}: {sample}{' ...' if len(params) > 10 else ''}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

