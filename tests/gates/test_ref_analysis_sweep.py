"""
Gate test: Reference analysis RPC sweep.

For every demo that has a ref pack, creates the project via API, then
calls get_reference_analysis for each declared object type and verifies
non-empty data is returned.

This replaces the former GUI E2E ref_sweep.spec.ts test — the reference
analysis pipeline is pure backend logic, no Electron needed.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from quantumvitas.api import QVService

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REF_PACKS_DIR = REPO_ROOT / "resources" / "demo_projects" / "ref_packs"


def _collect_ref_pack_demos():
    """Collect (slug, [types]) for every demo with a ref pack."""
    if not REF_PACKS_DIR.exists():
        return []
    items = []
    for d in sorted(REF_PACKS_DIR.iterdir()):
        manifest_path = d / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
            types = list((manifest.get("object_types") or {}).keys())
            if types:
                items.append((d.name, types))
        except Exception:
            continue
    return items


_REF_DEMOS = _collect_ref_pack_demos()


@pytest.mark.parametrize(
    "slug,ref_types",
    _REF_DEMOS,
    ids=[s for s, _ in _REF_DEMOS],
)
def test_reference_analysis_returns_data(slug, ref_types, tmp_path):
    """Create demo project and verify get_reference_analysis returns data."""
    project_dir = tmp_path / slug
    project_dir.mkdir()

    # 1. Create demo project
    result = QVService.create_demo_project(
        target_dir=str(project_dir),
        name=slug,
        demo_id=slug,
    )
    project_root = Path(result["project_root"])
    assert project_root.exists(), f"Project root not created: {project_root}"

    # 2. Get calculation selector
    svc = QVService(project_root)
    calc_dtos = svc.calculation.list()
    assert calc_dtos, f"No calculations in demo project {slug}"
    calc_selector = calc_dtos[0].meta.slug or calc_dtos[0].calc_ulid
    assert calc_selector, f"No calculation selector for {slug}"

    # 3. Verify get_reference_analysis for each type
    for ref_type in ref_types:
        data = svc.analysis.get_reference_analysis(
            calculation_selector=calc_selector,
            analysis_type=ref_type,
        )
        assert data is not None, (
            f"get_reference_analysis returned None for {slug}/{ref_type}"
        )
        # Should have status or actual data (not an empty dict)
        assert data, f"Empty reference data for {slug}/{ref_type}"
