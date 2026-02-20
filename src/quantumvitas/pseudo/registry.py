"""Pseudopotential library registry — maps vendored manifest to downloadable archives.

Loads ``resources/pseudo_libinfo/{CURRENT}/MANIFEST_PSEUDO_SEED.json`` and
provides lookup by ``(library_key, variant, version)`` triple.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArchiveInfo:
    """Resolved info for a downloadable pseudo archive."""

    filename: str  # e.g. "SSSP_1.3.0_PBE_precision.tar.gz"
    sha256: str
    size_bytes: int
    library_key: str  # user-facing key: "sssp", "pseudodojo", etc.
    dir_name: str  # install directory name: "SSSP", "PseudoDojo", etc.
    variant: str  # "precision", "nc-sr_pbe_standard", "pbe", "default"
    version: str  # "1.3.0", "0.4", "1.5", "current"
    companions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Category → (library_key, dir_name) mapping
# ---------------------------------------------------------------------------
_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "sssp": ("sssp", "SSSP"),
    "pseudo-dojo": ("pseudodojo", "PseudoDojo"),
    "gbrv": ("gbrv", "GBRV"),
    "sg15": ("sg15", "SG15"),
    "hgh": ("hgh", "HGH"),
    "pslibrary": ("ps-library", "PS-Library"),
    "gipaw": ("gipaw", "GIPAW"),
    "scan": ("scan_tm", "SCAN_TM"),
}

# Default variants per library (when user passes variant="")
_DEFAULT_VARIANTS: dict[str, str] = {
    "sssp": "precision",
    "pseudodojo": "nc-sr_pbe_standard",
    "gbrv": "pbe",
    "sg15": "oncv",
    "hgh": "default",
    "ps-library": "default",
    "gipaw": "default",
    "scan_tm": "default",
}


def _find_manifest_path() -> Path:
    """Find the vendored manifest JSON on disk."""
    # Walk up from this file to repo root
    current = Path(__file__).resolve().parent
    while current != current.parent:
        resources = current / "resources" / "pseudo_libinfo"
        if resources.is_dir():
            current_file = resources / "CURRENT"
            if current_file.exists():
                tag = current_file.read_text().strip()
                manifest = resources / tag / "MANIFEST_PSEUDO_SEED.json"
                if manifest.exists():
                    return manifest
        current = current.parent
    raise FileNotFoundError(
        "Could not find vendored MANIFEST_PSEUDO_SEED.json. "
        "Expected resources/pseudo_libinfo/{CURRENT}/MANIFEST_PSEUDO_SEED.json"
    )


def _compute_variant(entry: dict[str, Any], category: str) -> str:
    """Compute the variant string from a manifest entry."""
    if category == "sssp":
        return entry.get("quality", "unknown")

    if category == "pseudo-dojo":
        pp_type = entry.get("type") or "nc"
        rel = entry.get("relativistic") or "sr"
        xc = entry.get("xc") or "pbe"
        quality = entry.get("quality") or "standard"
        return f"{pp_type}-{rel}_{xc}_{quality}"

    if category == "gbrv":
        # Extract xc from filename: GBRV_pbe_UPF_v1.5.tar.gz → pbe
        fname = Path(entry["relative_path"]).name.lower()
        for xc in ("pbe", "lda", "pbesol"):
            if f"_{xc}_" in fname:
                return xc
        return "pbe"

    if category == "sg15":
        return "oncv"

    if category == "pslibrary":
        ver = entry.get("library_version") or ""
        return "legacy" if ver == "legacy" else "default"

    # hgh, gipaw, scan → single-variant
    return "default"


def _compute_version(entry: dict[str, Any], category: str) -> str:
    """Compute the version string from a manifest entry."""
    raw = entry.get("library_version")

    if raw is None:
        return "current"

    if category == "pseudo-dojo":
        # "04" → "0.4", "11" → "1.1"
        if raw.isdigit() and len(raw) == 2:
            return f"{raw[0]}.{raw[1]}"
        return raw

    return str(raw)


class PseudoRegistry:
    """Registry of downloadable pseudo libraries from the vendored manifest."""

    def __init__(self) -> None:
        self._archives: dict[str, ArchiveInfo] = {}  # filename → info
        self._by_key: dict[tuple[str, str, str], ArchiveInfo] = {}
        self._load_manifest()

    # ------------------------------------------------------------------
    def _load_manifest(self) -> None:
        manifest_path = _find_manifest_path()
        data = json.loads(manifest_path.read_text())

        files_list: list[dict[str, Any]] = []
        if isinstance(data, dict):
            files_list = data.get("files", data.get("entries", []))
        elif isinstance(data, list):
            files_list = data

        # First pass: build archives (skip companion JSONs for now)
        companion_map: dict[str, list[str]] = {}  # key → companion filenames

        for entry in files_list:
            category = entry.get("category", "")
            if category not in _CATEGORY_MAP:
                logger.debug("Skipping unknown category %r", category)
                continue

            library_key, dir_name = _CATEGORY_MAP[category]
            variant = _compute_variant(entry, category)
            version = _compute_version(entry, category)
            filename = Path(entry["relative_path"]).name
            rel_path = entry["relative_path"]

            # Detect companion files (SSSP .json cutoffs)
            is_archive = any(
                rel_path.endswith(ext) for ext in (".tar.gz", ".tgz", ".tar", ".zip")
            )
            if not is_archive:
                # It's a companion file — record it
                key_tuple = (library_key, variant, version)
                companion_map.setdefault(key_tuple, []).append(filename)
                continue

            info = ArchiveInfo(
                filename=filename,
                sha256=entry["sha256"],
                size_bytes=entry["size_bytes"],
                library_key=library_key,
                dir_name=dir_name,
                variant=variant,
                version=version,
            )
            self._archives[filename] = info
            key = (library_key, variant, version)
            self._by_key[key] = info

        # Second pass: attach companions
        for key, companions in companion_map.items():
            if key in self._by_key:
                info = self._by_key[key]
                # ArchiveInfo is frozen, so rebuild with companions
                new_info = ArchiveInfo(
                    filename=info.filename,
                    sha256=info.sha256,
                    size_bytes=info.size_bytes,
                    library_key=info.library_key,
                    dir_name=info.dir_name,
                    variant=info.variant,
                    version=info.version,
                    companions=companions,
                )
                self._archives[info.filename] = new_info
                self._by_key[key] = new_info

    # ------------------------------------------------------------------
    def resolve(
        self, library: str, variant: str = "", version: str = "latest"
    ) -> ArchiveInfo:
        """Resolve ``(library, variant, version)`` to archive info.

        Raises ``ValueError`` if no matching archive exists.
        """
        library = library.lower().strip()

        if not variant:
            variant = self.get_default_variant(library)

        if version == "latest" or not version:
            # Pick the first matching (library, variant, *) — manifest is
            # sorted with latest versions first in practice.
            candidates = [
                info
                for info in self._by_key.values()
                if info.library_key == library and info.variant == variant
            ]
            if not candidates:
                available = self.list_variants(library)
                raise ValueError(
                    f"No archive found for library={library!r}, variant={variant!r}. "
                    f"Available variants: {available}"
                )
            # Sort by version descending (simple string sort suffices for semver-like)
            candidates.sort(key=lambda i: i.version, reverse=True)
            return candidates[0]

        key = (library, variant, version)
        if key in self._by_key:
            return self._by_key[key]

        # Try to provide a helpful error
        available = self.list_variants(library)
        raise ValueError(
            f"No archive found for library={library!r}, variant={variant!r}, "
            f"version={version!r}. Available variants: {available}"
        )

    # ------------------------------------------------------------------
    def list_libraries(self) -> list[dict[str, Any]]:
        """List all available libraries with their variants and versions."""
        libs: dict[str, dict[str, Any]] = {}
        for info in self._by_key.values():
            if info.library_key not in libs:
                libs[info.library_key] = {
                    "library_key": info.library_key,
                    "dir_name": info.dir_name,
                    "variants": set(),
                    "versions": set(),
                    "archives": 0,
                }
            libs[info.library_key]["variants"].add(info.variant)
            libs[info.library_key]["versions"].add(info.version)
            libs[info.library_key]["archives"] += 1

        result = []
        for lib in sorted(libs.values(), key=lambda x: x["library_key"]):
            result.append(
                {
                    "library_key": lib["library_key"],
                    "dir_name": lib["dir_name"],
                    "default_variant": _DEFAULT_VARIANTS.get(
                        lib["library_key"], "default"
                    ),
                    "variants": sorted(lib["variants"]),
                    "versions": sorted(lib["versions"]),
                    "n_archives": lib["archives"],
                }
            )
        return result

    # ------------------------------------------------------------------
    def get_default_variant(self, library: str) -> str:
        """Get recommended default variant for a library."""
        library = library.lower().strip()
        if library not in _DEFAULT_VARIANTS:
            raise ValueError(
                f"Unknown library {library!r}. "
                f"Available: {sorted(_DEFAULT_VARIANTS.keys())}"
            )
        return _DEFAULT_VARIANTS[library]

    # ------------------------------------------------------------------
    def list_variants(self, library: str) -> list[str]:
        """List available variants for a library."""
        library = library.lower().strip()
        variants: set[str] = set()
        for info in self._by_key.values():
            if info.library_key == library:
                variants.add(info.variant)
        return sorted(variants)
