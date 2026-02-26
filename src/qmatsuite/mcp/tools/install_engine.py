"""install_engine tool — install a computation engine via conda or GitHub release."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def install_engine(engine: str, version: str = "", source: str = "auto") -> dict:
    """Install a computation engine automatically via conda/micromamba or GitHub release.

    Args:
        engine: Engine family key (e.g. 'xtb', 'qe', 'lammps').
        version: Optional version string. Empty string means latest.
        source: Installation source — 'auto', 'conda', or 'github_release'.
    """
    from qmatsuite.core.engines.engine_meta import ENGINE_META

    family = (engine or "").strip().lower()
    if family not in ENGINE_META:
        return make_error(
            "unknown_engine",
            f"Unknown engine '{engine}'. Use list_engines() to see available engines.",
            context_hint="Use list_engines() to see all supported engine families.",
        )

    # Detect commercial/manual-only engines (no conda_package and no github_release path)
    meta = ENGINE_META[family]
    has_conda = bool(meta.get("conda_package"))
    has_github = family == "qe"  # Only QE has github_release support
    if not has_conda and not has_github:
        return make_error(
            "manual_only_engine",
            f"Engine '{family}' ({meta.get('display_name', family)}) cannot be auto-installed. "
            "It requires a manual installation or a license.",
            context_hint="Use register_engine_path(engine='...', path='...') to register a manually installed engine.",
        )

    from qmatsuite.api.engines import install_engine as api_install_engine

    progress_events: list[dict] = []

    def _on_progress(**kw):
        progress_events.append(kw)

    try:
        result = api_install_engine(
            family,
            version=version or None,
            source=source or "auto",
            on_progress=_on_progress,
        )
    except ValueError as exc:
        return make_error(
            "install_failed",
            str(exc),
            context_hint="Check engine name and source. Use list_installable_engines() to see available options.",
        )

    last_stage = None
    for ev in reversed(progress_events):
        if "stage" in ev:
            last_stage = ev["stage"]
            break

    data = {
        "engine": result.get("engine", family),
        "source": result.get("source", source),
        "installation": result.get("installation", {}),
    }
    if last_stage:
        data["last_stage"] = last_stage

    return make_response(
        data,
        context_hint=(
            f"Use verify_engine(engine='{family}') to validate the installation, "
            f"then list_engines(installed_only=True) to confirm it appears."
        ),
    )
