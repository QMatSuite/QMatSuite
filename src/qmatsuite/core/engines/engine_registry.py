"""Distribution engine registry persisted in engines.json."""

from __future__ import annotations

import json
import logging
import platform
import re
import shutil
import subprocess
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qmatsuite.core.paths import get_app_data_dir, home_config_dir, home_engines_dir

from .engine_meta import ENGINE_META, get_detection_binaries, get_platform_primary_binary
from .version_probe import run_version_probe

logger = logging.getLogger(__name__)

ENGINE_REGISTRY_SCHEMA_VERSION = 1
USER_SOURCES = {"user_path", "user_venv"}
ACTIVE_SOURCE_PRIORITY = [
    "user_path",
    "user_venv",
    "bundled",
    "micromamba",
    "github_release",
    "system_path",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _binary_name_variants(binary_name: str) -> List[str]:
    """Return common cross-platform name variants for one executable."""
    out = [binary_name]
    if binary_name.endswith(".x"):
        out.append(binary_name.replace(".x", ".exe"))
        out.append(f"{binary_name}.exe")
    elif binary_name.endswith(".exe"):
        out.append(binary_name.replace(".exe", ""))
    else:
        out.append(f"{binary_name}.exe")
    # Preserve order while deduplicating
    seen = set()
    ordered = []
    for item in out:
        if item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def _resolve_binary_in_path(base_path: Path, binary_name: str) -> Optional[Path]:
    """Resolve one executable inside a bin directory or direct-binary path."""
    if base_path.is_file():
        if base_path.name in _binary_name_variants(binary_name):
            return base_path
        return None
    if not base_path.is_dir():
        return None

    for variant in _binary_name_variants(binary_name):
        candidate = base_path / variant
        if candidate.is_file():
            return candidate
    return None


def _installation_key(installation: Dict[str, Any]) -> Tuple[str, str, str, str]:
    source = str(installation.get("source") or "")
    path = str(installation.get("path") or "")
    pyexe = str(installation.get("python_executable") or "")
    conda_env = str(installation.get("conda_env") or "")
    return (source, path, pyexe, conda_env)


def _find_python_executable(env_dir: Path) -> Optional[Path]:
    candidates = [
        env_dir / "bin" / "python",
        env_dir / "bin" / "python3",
        env_dir / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class EngineRegistry:
    """CRUD + discovery for `<app_data>/config/engines.json`."""

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or (home_config_dir() / "engines.json")
        self._data: Optional[Dict[str, Any]] = None

    @staticmethod
    def _default_data() -> Dict[str, Any]:
        return {
            "schema_version": ENGINE_REGISTRY_SCHEMA_VERSION,
            "engines": {},
        }

    @staticmethod
    def _normalize_engine_entry(value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return {"installations": [], "active": None}
        installations = value.get("installations")
        if not isinstance(installations, list):
            installations = []
        active = value.get("active")
        if not isinstance(active, str):
            active = None
        return {"installations": installations, "active": active}

    def load(self) -> Dict[str, Any]:
        """Load engines.json; create a default file if missing."""
        if self._data is not None:
            return self._data

        if not self.registry_path.exists():
            self._data = self._default_data()
            return self._data

        try:
            raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("engine registry must be a JSON object")
        except Exception as exc:
            logger.warning("Failed to load engine registry (%s): resetting", exc)
            self._data = self._default_data()
            self.save()
            return self._data

        schema_version = raw.get("schema_version")
        if schema_version != ENGINE_REGISTRY_SCHEMA_VERSION:
            logger.warning(
                "Unsupported engine registry schema_version=%s (expected %s); preserving payload",
                schema_version,
                ENGINE_REGISTRY_SCHEMA_VERSION,
            )
        engines = raw.get("engines")
        if not isinstance(engines, dict):
            engines = {}

        normalized = self._default_data()
        normalized["schema_version"] = schema_version or ENGINE_REGISTRY_SCHEMA_VERSION
        normalized["engines"] = {
            str(engine): self._normalize_engine_entry(entry)
            for engine, entry in engines.items()
        }
        self._data = normalized
        return normalized

    def save(self) -> None:
        """Atomically persist registry JSON."""
        data = self._data or self._default_data()
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = self.registry_path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self.registry_path)

    def list_all(self) -> Dict[str, Any]:
        return self.load()

    def list_installations(self, engine_family: str) -> List[Dict[str, Any]]:
        data = self.load()
        entry = self._normalize_engine_entry(data.get("engines", {}).get(engine_family))
        return list(entry["installations"])

    def get_active(self, engine_family: str) -> Optional[Dict[str, Any]]:
        data = self.load()
        entry = self._normalize_engine_entry(data.get("engines", {}).get(engine_family))
        active_id = entry.get("active")
        if not active_id:
            return None
        for installation in entry["installations"]:
            if installation.get("id") == active_id:
                return dict(installation)
        return None

    def set_active(self, engine_family: str, installation_id: str) -> bool:
        data = self.load()
        engines = data.setdefault("engines", {})
        entry = self._normalize_engine_entry(engines.get(engine_family))
        if not any(inst.get("id") == installation_id for inst in entry["installations"]):
            return False
        entry["active"] = installation_id
        engines[engine_family] = entry
        self._data = data
        self.save()
        return True

    def add_installation(self, engine_family: str, installation: Dict[str, Any]) -> Dict[str, Any]:
        data = self.load()
        engines = data.setdefault("engines", {})
        entry = self._normalize_engine_entry(engines.get(engine_family))
        installations = list(entry["installations"])
        installation_id = installation.get("id")
        if not installation_id:
            raise ValueError("installation must include non-empty 'id'")

        replaced = False
        for idx, existing in enumerate(installations):
            if existing.get("id") == installation_id:
                installations[idx] = dict(installation)
                replaced = True
                break
        if not replaced:
            installations.append(dict(installation))

        entry["installations"] = installations
        if not entry.get("active"):
            entry["active"] = installation_id
        engines[engine_family] = entry
        self._data = data
        self.save()
        return dict(installation)

    def remove_installation(self, engine_family: str, installation_id: str) -> bool:
        data = self.load()
        engines = data.setdefault("engines", {})
        entry = self._normalize_engine_entry(engines.get(engine_family))
        original_len = len(entry["installations"])
        entry["installations"] = [
            inst for inst in entry["installations"] if inst.get("id") != installation_id
        ]
        if len(entry["installations"]) == original_len:
            return False
        if entry.get("active") == installation_id:
            entry["active"] = self._pick_active(entry["installations"])
        engines[engine_family] = entry
        self._data = data
        self.save()
        return True

    def discover(self, *, persist: bool = True) -> Dict[str, Any]:
        """
        Discover bundled/micromamba/PATH installations and merge with registry.

        User-managed entries (`user_path`, `user_venv`) are preserved.
        """
        data = self.load()
        engines = data.setdefault("engines", {})

        for engine_family in ENGINE_META:
            entry = self._normalize_engine_entry(engines.get(engine_family))
            existing = list(entry["installations"])

            discovered = []
            discovered.extend(self._scan_bundled(engine_family))
            discovered.extend(self._scan_micromamba(engine_family))
            discovered.extend(self._scan_system_path(engine_family))

            merged = self._merge_installations(existing, discovered)
            for installation in merged:
                verified, _ = self._verify_installation(engine_family, installation)
                installation["stale"] = not verified
                installation["verified"] = _utc_now_iso() if verified else None

            entry["installations"] = merged
            entry["active"] = self._pick_active(
                merged,
                preferred_id=entry.get("active"),
            )
            engines[engine_family] = entry

        self._data = data
        if persist:
            self.save()
        return data

    def _pick_active(
        self,
        installations: List[Dict[str, Any]],
        preferred_id: Optional[str] = None,
    ) -> Optional[str]:
        if preferred_id:
            for inst in installations:
                if inst.get("id") == preferred_id and not inst.get("stale", False):
                    return preferred_id

        by_source: Dict[str, List[Dict[str, Any]]] = {}
        for inst in installations:
            if inst.get("stale", False):
                continue
            source = str(inst.get("source") or "")
            by_source.setdefault(source, []).append(inst)

        for source in ACTIVE_SOURCE_PRIORITY:
            candidates = by_source.get(source, [])
            if candidates:
                return str(candidates[0].get("id"))

        for inst in installations:
            if not inst.get("stale", False):
                return str(inst.get("id"))
        return None

    def _merge_installations(
        self,
        existing: List[Dict[str, Any]],
        discovered: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        user_entries = [dict(inst) for inst in existing if inst.get("source") in USER_SOURCES]
        existing_discovered = [
            dict(inst) for inst in existing if inst.get("source") not in USER_SOURCES
        ]

        merged: List[Dict[str, Any]] = []
        merged.extend(user_entries)
        merged.extend(dict(inst) for inst in discovered)

        discovered_keys = {_installation_key(inst) for inst in discovered}
        for old in existing_discovered:
            if _installation_key(old) not in discovered_keys:
                old["stale"] = True
                merged.append(old)

        # Deduplicate by key while preserving first occurrence.
        deduped: List[Dict[str, Any]] = []
        seen = set()
        for inst in merged:
            key = _installation_key(inst)
            if key in seen:
                continue
            deduped.append(inst)
            seen.add(key)
        return deduped

    def _scan_bundled(self, engine_family: str) -> List[Dict[str, Any]]:
        meta = ENGINE_META[engine_family]
        if meta.get("engine_type") != "binary":
            return []

        installations: List[Dict[str, Any]] = []
        engine_dir = home_engines_dir() / engine_family
        candidates: List[Path] = []
        if engine_dir.is_dir():
            candidates.extend([p for p in engine_dir.iterdir() if p.is_dir()])

        # Wannier90 often ships inside QE bundles.
        if engine_family == "w90":
            qe_dir = home_engines_dir() / "qe"
            if qe_dir.is_dir():
                candidates.extend([p for p in qe_dir.iterdir() if p.is_dir()])

        for install_dir in sorted(candidates, reverse=True):
            bin_dir = install_dir / "bin"
            if not bin_dir.is_dir():
                continue

            found_binary = self._find_first_binary(engine_family, bin_dir)
            if not found_binary:
                continue

            source = "bundled"
            if install_dir.name.startswith("github-"):
                source = "github_release"

            version = self._extract_version_hint(install_dir.name)
            installations.append(
                {
                    "id": install_dir.name,
                    "source": source,
                    "version": version,
                    "path": str(bin_dir),
                    "required_binaries": [found_binary],
                    "env_vars": {},
                }
            )
        return installations

    def _scan_micromamba(self, engine_family: str) -> List[Dict[str, Any]]:
        meta = ENGINE_META[engine_family]
        envs_root = get_app_data_dir() / "micromamba" / "envs"
        if not envs_root.is_dir():
            return []

        installations: List[Dict[str, Any]] = []
        for env_dir in sorted(envs_root.iterdir()):
            if not env_dir.is_dir():
                continue
            env_name = env_dir.name

            if meta.get("engine_type") == "python":
                pyexe = _find_python_executable(env_dir)
                if not pyexe:
                    continue
                module = meta.get("python_import")
                if not module:
                    continue
                ok, version = self._check_python_import(pyexe, str(module))
                if not ok:
                    continue
                inst_id = f"conda-{version}" if version else f"conda-{env_name}"
                installations.append(
                    {
                        "id": inst_id,
                        "source": "micromamba",
                        "version": version,
                        "python_executable": str(pyexe),
                        "conda_env": env_name,
                        "env_vars": {},
                    }
                )
                continue

            bin_dir = env_dir / "bin"
            if not bin_dir.is_dir():
                bin_dir = env_dir / "Scripts"
            if not bin_dir.is_dir():
                continue

            found_binary = self._find_first_binary(engine_family, bin_dir)
            if not found_binary:
                continue

            version = self._detect_binary_version(engine_family, bin_dir, found_binary)
            inst_id = f"conda-{version}" if version else f"conda-{env_name}"
            installations.append(
                {
                    "id": inst_id,
                    "source": "micromamba",
                    "version": version,
                    "path": str(bin_dir),
                    "conda_env": env_name,
                    "required_binaries": [found_binary],
                    "env_vars": {},
                }
            )
        return installations

    def _scan_system_path(self, engine_family: str) -> List[Dict[str, Any]]:
        meta = ENGINE_META[engine_family]
        if meta.get("engine_type") != "binary":
            return []

        for binary in get_detection_binaries(engine_family):
            found = shutil.which(binary)
            if not found:
                continue
            found_path = Path(found).resolve()
            version = self._detect_binary_version(engine_family, found_path.parent, binary)
            return [
                {
                    "id": f"system-{found_path.name}",
                    "source": "system_path",
                    "version": version,
                    "path": str(found_path.parent),
                    "required_binaries": [binary],
                    "env_vars": {},
                }
            ]
        return []

    def _find_first_binary(self, engine_family: str, bin_dir: Path) -> Optional[str]:
        for binary in get_detection_binaries(engine_family):
            if _resolve_binary_in_path(bin_dir, binary):
                return binary
        return None

    def _extract_version_hint(self, token: str) -> Optional[str]:
        match = re.search(r"(\d+\.\d+(?:\.\d+)?)", token)
        return match.group(1) if match else None

    def _verify_installation(
        self,
        engine_family: str,
        installation: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        meta = ENGINE_META.get(engine_family, {})
        engine_type = meta.get("engine_type")

        if engine_type == "python":
            python_executable = installation.get("python_executable")
            if not python_executable:
                return False, "missing python_executable"
            pyexe = Path(str(python_executable))
            if not pyexe.is_file():
                return False, f"missing python executable: {pyexe}"
            module = str(meta.get("python_import") or "")
            ok, version = self._check_python_import(pyexe, module)
            if ok and version:
                installation["version"] = version
            if not ok:
                return False, f"python import failed for {module}"
            # Verify pip requirements
            pip_reqs = meta.get("pip_requirements", {})
            for pip_name, import_name in pip_reqs.items():
                dep_ok, _ = self._check_python_import(pyexe, import_name)
                if not dep_ok:
                    return False, f"pip dependency '{pip_name}' (import: {import_name}) not importable"
            return True, None

        base_path = Path(str(installation.get("path") or ""))
        if not base_path.exists():
            return False, f"path does not exist: {base_path}"

        required = list(installation.get("required_binaries") or [])
        if not required:
            required = list(meta.get("required_binaries") or [])
        if not required:
            primary = get_platform_primary_binary(engine_family)
            if primary:
                required = [primary]

        resolved_binary: Optional[Path] = None
        for binary in required:
            resolved_binary = _resolve_binary_in_path(base_path, binary)
            if resolved_binary:
                break
        if not resolved_binary:
            # Fall back to broader detection order for compatibility.
            for binary in get_detection_binaries(engine_family):
                resolved_binary = _resolve_binary_in_path(base_path, binary)
                if resolved_binary:
                    break
        if not resolved_binary:
            return False, f"required binaries not found in {base_path}"

        # Check executable permission (non-Windows)
        if platform.system() != "Windows":
            st = resolved_binary.stat()
            if not (st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
                return False, (
                    f"binary lacks execute permission: {resolved_binary}. "
                    f"Fix with: chmod +x \"{resolved_binary}\""
                )

        version = self._detect_binary_version(
            engine_family=engine_family,
            bin_dir=resolved_binary.parent,
            binary_name=resolved_binary.name,
        )
        has_version_command = bool(meta.get("version_command"))
        if has_version_command and version is None:
            return False, f"version probe failed for {resolved_binary}"
        if version:
            installation["version"] = version

        return True, None

    def _detect_binary_version(
        self,
        engine_family: str,
        bin_dir: Path,
        binary_name: str,
    ) -> Optional[str]:
        meta = ENGINE_META.get(engine_family, {})
        version_command = meta.get("version_command")
        if not version_command:
            return None
        if not isinstance(version_command, list) or not version_command:
            return None

        # Replace command executable token with the resolved binary path.
        resolved_binary = _resolve_binary_in_path(bin_dir, binary_name)
        if not resolved_binary:
            primary = get_platform_primary_binary(engine_family)
            if primary:
                resolved_binary = _resolve_binary_in_path(bin_dir, primary)
        if not resolved_binary:
            return None

        command = list(version_command)
        command[0] = str(resolved_binary)
        result = run_version_probe(command, timeout=10)
        if result is None:
            return None

        output = (result.stdout or "") + "\n" + (result.stderr or "")
        output = output.strip()
        if not output:
            return None
        regex = meta.get("version_regex")
        if isinstance(regex, str):
            match = re.search(regex, output)
            if match:
                return match.group(1)
        if result.returncode != 0:
            return None
        first_line = output.splitlines()[0].strip()
        return first_line or None

    def _check_python_import(self, pyexe: Path, module_name: str) -> Tuple[bool, Optional[str]]:
        if not module_name:
            return False, None
        try:
            result = subprocess.run(
                [str(pyexe), "-c", f"import {module_name}; print({module_name}.__version__)"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except Exception:
            return False, None
        if result.returncode != 0:
            return False, None
        version = (result.stdout or "").strip() or None
        return True, version

    def get_active_binary(
        self,
        engine_family: str,
        binary_name: Optional[str] = None,
    ) -> Optional[Path]:
        installation = self.get_active(engine_family)
        if not installation:
            return None
        base = Path(str(installation.get("path") or ""))
        candidates: List[str] = []
        if binary_name:
            candidates.append(binary_name)
        required = installation.get("required_binaries") or []
        candidates.extend(required)
        candidates.extend(get_detection_binaries(engine_family))

        seen = set()
        for name in candidates:
            if not name or name in seen:
                continue
            seen.add(name)
            resolved = _resolve_binary_in_path(base, name)
            if resolved:
                return resolved
        return None

    def get_active_python(self, engine_family: str) -> Optional[Path]:
        installation = self.get_active(engine_family)
        if not installation:
            return None
        pyexe = installation.get("python_executable")
        if not pyexe:
            return None
        path = Path(str(pyexe))
        return path if path.is_file() else None

    def verify_engine(self, engine_family: str) -> Tuple[bool, str]:
        installation = self.get_active(engine_family)
        if not installation:
            return False, f"Engine '{engine_family}' has no active installation."
        ok, reason = self._verify_installation(engine_family, installation)
        if not ok:
            return False, reason or f"Engine '{engine_family}' verification failed."
        return True, "OK"


def get_registry(registry_path: Optional[Path] = None) -> EngineRegistry:
    return EngineRegistry(registry_path=registry_path)


def resolve_active_binary(
    engine_family: str,
    binary_name: Optional[str] = None,
    *,
    auto_discover: bool = False,
) -> Optional[Path]:
    registry = EngineRegistry()
    if auto_discover:
        registry.discover()
    else:
        registry.load()
    return registry.get_active_binary(engine_family, binary_name=binary_name)


def resolve_active_python(
    engine_family: str,
    *,
    auto_discover: bool = False,
) -> Optional[Path]:
    registry = EngineRegistry()
    if auto_discover:
        registry.discover()
    else:
        registry.load()
    return registry.get_active_python(engine_family)


def discover_registry() -> Dict[str, Any]:
    registry = EngineRegistry()
    return registry.discover(persist=True)
