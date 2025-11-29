from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import configparser


@dataclass
class InputTestCase:
    """
    Canonical description of a QE test input discovered under ci_test_data/.

    Attributes:
        input_path: Absolute path to the QE input file.
        reference_path: Optional path to the reference output (benchmark or .out).
        args: Optional argument string pulled from legacy jobconfig (if available).
        sequence: 1-based ordering for execution.
    """

    input_path: Path
    reference_path: Optional[Path]
    args: Optional[str] = None
    sequence: int = 0


def load_test_cases(
    folder: Path,
    *,
    ci_root: Optional[Path] = None,
    root_jobconfig: Optional[Path] = None,
    write_local_jobconfig: bool = True,
) -> List[InputTestCase]:
    """
    Load (or discover) QE test cases for a ci_test_data subdirectory.

    If ``jobconfig.json`` exists under ``folder``, it is used directly. Otherwise,
    this function applies the heuristics described below, optionally writing the
    discovered metadata back to ``jobconfig.json`` for future runs.

    Discovery heuristics:
        1. Inputs are all ``*.in`` files (top-level if present, otherwise recursive).
        2. If any file name contains ``benchmark``, it is treated as a reference
           output, matched to the input whose filename appears within it.
        3. If no benchmark is found, search for ``*.out`` with the same stem.
        4. If a global jobconfig (INI format) exists, its ``inputs_args`` order is
           used to set the sequence and carry over the ``args`` metadata.
    """

    folder = Path(folder).resolve()
    ci_root = ci_root.resolve() if ci_root else _guess_ci_root(folder)
    if root_jobconfig is None and ci_root:
        candidate = ci_root / "jobconfig"
        root_jobconfig = candidate if candidate.exists() else None

    local_cases = _read_local_jobconfig(folder)
    if local_cases is not None:
        return local_cases

    cases = _discover_cases(folder, ci_root, root_jobconfig)
    if write_local_jobconfig and cases:
        _write_local_jobconfig(folder, cases)
    return cases


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _guess_ci_root(folder: Path) -> Optional[Path]:
    for current in [folder] + list(folder.parents):
        jobconfig_file = current / "jobconfig"
        if jobconfig_file.exists():
            return current
    return None


def _read_local_jobconfig(folder: Path) -> Optional[List[InputTestCase]]:
    json_path = folder / "jobconfig.json"
    if not json_path.exists():
        return None

    try:
        data = json.loads(json_path.read_text())
    except json.JSONDecodeError:
        return None

    tests: List[InputTestCase] = []
    for entry in data.get("tests", []):
        input_rel = entry.get("input")
        if not input_rel:
            continue
        input_path = _resolve_relative(folder, input_rel)
        reference_rel = entry.get("reference")
        reference_path = (
            _resolve_relative(folder, reference_rel) if reference_rel else None
        )
        args = entry.get("args")
        sequence = entry.get("sequence", len(tests) + 1)
        tests.append(
            InputTestCase(
                input_path=input_path,
                reference_path=reference_path,
                args=args,
                sequence=sequence,
            )
        )

    tests.sort(key=lambda case: (case.sequence, case.input_path.name))
    for idx, case in enumerate(tests, 1):
        case.sequence = idx
    return tests


def _write_local_jobconfig(folder: Path, cases: Sequence[InputTestCase]) -> None:
    json_path = folder / "jobconfig.json"
    payload = {
        "version": 1,
        "tests": [
            {
                "input": _relativize(case.input_path, folder),
                "reference": _relativize(case.reference_path, folder)
                if case.reference_path
                else None,
                "args": case.args,
                "sequence": case.sequence,
            }
            for case in cases
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2))


def _discover_cases(
    folder: Path,
    ci_root: Optional[Path],
    root_jobconfig: Optional[Path],
) -> List[InputTestCase]:
    inputs = sorted(folder.glob("*.in"))
    if not inputs:
        inputs = sorted(folder.rglob("*.in"))
    inputs = [path for path in inputs if "benchmark" not in path.name]
    if not inputs:
        raise FileNotFoundError(f"No QE input files found under {folder}")

    section_name = _section_name(folder, ci_root)
    order_entries = _load_global_section(root_jobconfig, section_name)
    order_lookup: Dict[str, Tuple[int, Optional[str]]] = {}
    if order_entries:
        for idx, entry in enumerate(order_entries, 1):
            name = entry.get("name")
            if name:
                order_lookup[name] = (idx, entry.get("args"))

    next_sequence = len(order_lookup) + 1
    benchmarks = list(folder.rglob("*benchmark*"))
    cases: List[InputTestCase] = []

    for input_path in inputs:
        lookup = order_lookup.get(input_path.name)
        if lookup:
            seq, args = lookup
        else:
            seq, args = next_sequence, None
            next_sequence += 1

        reference_path = _find_reference_file(folder, input_path, benchmarks)
        cases.append(
            InputTestCase(
                input_path=input_path,
                reference_path=reference_path,
                args=args,
                sequence=seq,
            )
        )

    cases.sort(key=lambda case: (case.sequence, case.input_path.name))
    for idx, case in enumerate(cases, 1):
        case.sequence = idx
    return cases


def _find_reference_file(
    folder: Path, input_path: Path, benchmarks: Sequence[Path]
) -> Optional[Path]:
    for bench in benchmarks:
        if input_path.name in bench.name:
            return bench.resolve()

    candidate_name = input_path.with_suffix(".out").name
    candidates = sorted(folder.rglob(candidate_name))
    if candidates:
        return candidates[0].resolve()
    return None


def _section_name(folder: Path, ci_root: Optional[Path]) -> str:
    if ci_root:
        try:
            rel = folder.relative_to(ci_root)
            return rel.as_posix()
        except ValueError:
            pass
    return folder.name


def _relativize(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except Exception:
        return str(path)


def _resolve_relative(base: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (base / candidate).resolve()


def _load_global_section(
    jobconfig_path: Optional[Path], section_name: str
) -> Optional[List[Dict[str, Optional[str]]]]:
    if not jobconfig_path or not jobconfig_path.exists():
        return None
    mapping = _parse_global_jobconfig(jobconfig_path.resolve())
    section = section_name.rstrip("/")
    if section in mapping:
        return mapping[section]
    # Fall back to last component if relative path had directories
    if "/" in section:
        tail = section.split("/")[-1]
        return mapping.get(tail)
    return None


@lru_cache(maxsize=None)
def _parse_global_jobconfig(jobconfig_path: Path) -> Dict[str, List[Dict[str, Optional[str]]]]:
    config = configparser.ConfigParser()
    config.read(jobconfig_path)
    mapping: Dict[str, List[Dict[str, Optional[str]]]] = {}

    for section in config.sections():
        base = section.rstrip("/")
        value = config[section].get("inputs_args")
        if not value:
            continue
        try:
            parsed = eval(value, {}, {})
        except Exception:
            continue
        entries: List[Dict[str, Optional[str]]] = []
        for idx, item in enumerate(parsed, 1):
            if not isinstance(item, tuple) or not item:
                continue
            name = item[0]
            args = item[1] if len(item) > 1 else None
            entries.append({"name": name, "args": args, "sequence": idx})
        mapping[base] = entries
    return mapping


