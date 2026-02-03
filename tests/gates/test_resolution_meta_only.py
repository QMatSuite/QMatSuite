"""
Gate test G-K7-res: resolution.py index building uses meta-only loaders.

Enforces Law K7 (Spec §2.2): during index building and resolution scanning,
resolution.py must use load_yaml_meta_subtree / load_json_meta_subtree
instead of full-document loaders (CalcDoc.load, StepDoc.load, ProjectDoc.load).

The step_type_spec field must not be used as a resolution strategy (beyond-meta).

Allowlisted exceptions:
- POST-resolution full doc loads for ResolvedResource.entry backward compat
- ProjectDoc.load for project config (not index building)
"""

import re
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).parent.parent.parent / "src" / "quantumvitas"
RESOLUTION_FILE = SRC_ROOT / "core" / "resolution.py"

# ---- Check 1: No full-doc loaders in index building / resolution scanning ----

FULL_DOC_LOAD_RE = re.compile(
    r"(CalcDoc\.load|StepDoc\.load|ProjectDoc\.load)\s*\("
)


def _find_full_doc_loads() -> list[tuple[int, str]]:
    """Find CalcDoc/StepDoc/ProjectDoc .load() calls in resolution.py."""
    source = RESOLUTION_FILE.read_text()
    results = []
    for i, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if FULL_DOC_LOAD_RE.search(line):
            results.append((i, stripped))
    return results


def test_no_full_doc_load_in_index_building():
    """resolution.py must not use CalcDoc/StepDoc.load() during index building.

    Only load_yaml_meta_subtree / load_json_meta_subtree are allowed for
    index building and resolution scanning. Full doc loads are only allowed
    for POST-resolution ResolvedResource.entry or project config.
    """
    hits = _find_full_doc_loads()

    # Filter out allowlisted patterns
    unexpected = []
    for lineno, src in hits:
        if "ProjectDoc.load" in src:
            continue  # Allowlisted: project config
        if "load_yaml_doc" in src:
            continue  # POST-resolution entry data
        unexpected.append((lineno, src))

    if unexpected:
        lines = [
            f"\nG-K7-res FAILED: {len(unexpected)} full-doc loader(s) in resolution.py:\n"
        ]
        for lineno, src in sorted(unexpected):
            lines.append(f"  line {lineno}: {src}")
        lines.append("")
        lines.append(
            "Fix: Use load_yaml_meta_subtree() or load_json_meta_subtree() "
            "for index building and resolution scanning."
        )
        pytest.fail("\n".join(lines))


# ---- Check 2: No step_type_spec in resolution strategies ----

STEP_TYPE_SPEC_RE = re.compile(r"""\.get\(\s*["']step_type_spec["']\s*\)""")


def test_no_step_type_spec_resolution():
    """resolution.py must not use step_type_spec as a resolution strategy.

    step_type_spec is a semantic field (beyond-meta). Resolution must use
    only meta identity fields: ulid, name, slug, path.
    """
    source = RESOLUTION_FILE.read_text()
    violations = []

    for i, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if STEP_TYPE_SPEC_RE.search(line):
            violations.append((i, stripped))

    if violations:
        lines = [
            f"\nG-K7-res FAILED: {len(violations)} step_type_spec read(s) in resolution.py:\n"
        ]
        for lineno, src in sorted(violations):
            lines.append(f"  line {lineno}: {src}")
        lines.append("")
        lines.append(
            "Fix: Use meta identity fields (ulid, name, slug) for resolution, "
            "not semantic fields like step_type_spec."
        )
        pytest.fail("\n".join(lines))


# ---- Check 3: Index building functions use meta-only loaders ----


def test_index_building_uses_meta_loaders():
    """build_resource_index() must use load_yaml_meta_subtree / load_json_meta_subtree."""
    source = RESOLUTION_FILE.read_text()

    # Find the build_resource_index function body
    lines = source.splitlines()
    in_function = False
    func_lines: list[tuple[int, str]] = []

    for i, line in enumerate(lines, start=1):
        if "def build_resource_index(" in line:
            in_function = True
            func_lines = []
            continue
        if in_function:
            # Detect end of function by next def at same indentation
            if line.strip().startswith("def ") and not line.startswith("    "):
                break
            if line.strip().startswith("def ") and line.startswith("def "):
                break
            func_lines.append((i, line))

    # Verify meta-only loaders are used
    has_meta_yaml = any("load_yaml_meta_subtree" in line for _, line in func_lines)
    has_meta_json = any("load_json_meta_subtree" in line for _, line in func_lines)

    assert has_meta_yaml, (
        "build_resource_index() must use load_yaml_meta_subtree() for YAML files"
    )
    assert has_meta_json, (
        "build_resource_index() must use load_json_meta_subtree() for JSON structure files"
    )

    # Verify NO full-doc loaders
    full_doc_in_func = [
        (lineno, line.strip())
        for lineno, line in func_lines
        if FULL_DOC_LOAD_RE.search(line) and not line.strip().startswith("#")
    ]
    if full_doc_in_func:
        lines_msg = [
            f"\nbuild_resource_index() uses full-doc loader(s) — must use meta-only:\n"
        ]
        for lineno, src in full_doc_in_func:
            lines_msg.append(f"  line {lineno}: {src}")
        pytest.fail("\n".join(lines_msg))
