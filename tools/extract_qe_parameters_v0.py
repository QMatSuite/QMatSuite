#!/usr/bin/env python3
"""
Utility to scrape Quantum ESPRESSO input documentation and build a
module -> {section -> parameters} map.

The output is written to JSON and consumed by the CLI (`qms params`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib import error, request

from bs4 import BeautifulSoup  # type: ignore

DEFAULT_PATTERN = "https://www.quantum-espresso.org/Doc/INPUT_{name}.html"


@dataclass
class ModuleSpec:
    name: str
    doc_url: Optional[str] = None
    doc_name: Optional[str] = None
    aliases: List[str] = field(default_factory=list)


DEFAULT_MODULES: List[ModuleSpec] = [
    ModuleSpec("pw"),
    ModuleSpec("ph"),
    ModuleSpec("q2r"),
    ModuleSpec("matdyn"),
    ModuleSpec("pp"),
    ModuleSpec("bands"),
    ModuleSpec("dos"),
    ModuleSpec("projwfc"),
    ModuleSpec("neb"),
    ModuleSpec("cp"),
    ModuleSpec("ld1"),
    ModuleSpec("hp"),
    ModuleSpec("pwcond"),
    ModuleSpec("postahc"),
    ModuleSpec("dynmat"),
    ModuleSpec("oscdft_et"),
    ModuleSpec("oscdft_pp"),
    ModuleSpec("band_interpolation"),
    ModuleSpec("cppp"),
    ModuleSpec("d3hess"),
    ModuleSpec("ppacf"),
    ModuleSpec("pprism"),
]


def build_request(url: str) -> request.Request:
    return request.Request(
        url,
        headers={
            "User-Agent": "QMatSuite-DocExtractor/1.0 (+https://qmatsuite.org)"
        },
    )


def fetch_html(url: str) -> str:
    with request.urlopen(build_request(url), timeout=30) as response:
        data = response.read()
        return data.decode("utf-8", errors="ignore")


def normalize_section_name(text: str) -> Optional[str]:
    if not text:
        return None
    text = text.strip()
    match = re.search(r"&[A-Za-z0-9_]+", text)
    if match:
        return match.group(0).upper()
    clean = re.sub(r"[^A-Z0-9_]", " ", text).strip()
    if clean and clean.upper() == clean and len(clean) <= 64:
        return clean.replace(" ", "_")
    return None


def normalize_param_name(text: str) -> Optional[str]:
    if not text:
        return None
    candidate = text.strip()
    candidate = re.sub(r"\s+", "_", candidate)
    if not candidate:
        return None
    lowered = candidate.lower()
    if lowered.startswith(("namelist", "card", "input_", "section", "table")):
        return None
    if len(candidate) < 2 or len(candidate) > 80:
        return None
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", candidate):
        return None
    return candidate


def extract_parameters(html: str) -> Dict[str, List[str]]:
    soup = BeautifulSoup(html, "html.parser")
    sections: Dict[str, set] = {}
    for node in soup.find_all(["p", "h3"]):
        if node.name == "h3":
            heading = node.get_text(" ", strip=True).lower()
            if "introduction" in heading:
                break
            continue
        if node.name != "p":
            continue
        anchor = node.find("a")
        if not anchor:
            continue
        section_name = normalize_section_name(anchor.get_text(" ", strip=True))
        if not section_name:
            continue
        sibling = node.next_sibling
        while sibling is not None and getattr(sibling, "name", None) is None:
            sibling = sibling.next_sibling
        if sibling is None or sibling.name != "blockquote":
            continue
        params = set()
        for link in sibling.find_all("a"):
            param = normalize_param_name(link.get_text(" ", strip=True))
            if param:
                params.add(param)
        if params:
            sections.setdefault(section_name, set()).update(params)
    return {k: sorted(v) for k, v in sections.items() if v}


def load_module_specs(
    names: Optional[Iterable[str]], use_pattern_only: bool
) -> List[ModuleSpec]:
    base = {spec.name.lower(): spec for spec in DEFAULT_MODULES}
    if not names:
        return list(base.values())
    specs = []
    for name in names:
        key = name.lower()
        if key in base and not use_pattern_only:
            specs.append(base[key])
        else:
            specs.append(ModuleSpec(name=key))
    return specs


def resolve_url(spec: ModuleSpec, pattern: str, use_pattern_only: bool) -> str:
    if spec.doc_url and not use_pattern_only:
        return spec.doc_url
    doc_name = spec.doc_name or spec.name.upper().replace("-", "_")
    return pattern.format(name=doc_name.upper())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract QE module parameter metadata from official docs."
    )
    parser.add_argument(
        "--modules",
        nargs="*",
        help="Limit extraction to specific module names (default: built-in list).",
    )
    parser.add_argument(
        "--pattern",
        default=DEFAULT_PATTERN,
        help="Format string for documentation URLs (default: %(default)s)",
    )
    parser.add_argument(
        "--pattern-only",
        action="store_true",
        help="Ignore hard-coded URLs and compute every link via --pattern.",
    )
    parser.add_argument(
        "--output",
        default="src/qmatsuite/data/qe_module_parameters.json",
        help="Destination JSON file (default: %(default)s)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output for readability.",
    )
    args = parser.parse_args()

    specs = load_module_specs(args.modules, args.pattern_only)
    results: Dict[str, Dict[str, Any]] = {}
    failures: Dict[str, str] = {}

    for spec in specs:
        url = resolve_url(spec, args.pattern, args.pattern_only)
        try:
            html = fetch_html(url)
        except error.URLError as exc:
            failures[spec.name] = f"{exc}"
            continue

        sections = extract_parameters(html)
        if not sections:
            failures[spec.name] = "No sections/parameters detected"
            continue

        results[spec.name] = {
            "doc_url": url,
            "sections": sections,
        }

    if failures:
        sys.stderr.write("Some modules could not be processed:\n")
        for name, reason in failures.items():
            sys.stderr.write(f"  - {name}: {reason}\n")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module_count": len(results),
        "doc_pattern": args.pattern,
        "modules": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2 if args.pretty else None, sort_keys=False)
        handle.write("\n")

    sys.stdout.write(
        f"Wrote parameter map for {len(results)} modules to {output_path}\n"
    )
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

