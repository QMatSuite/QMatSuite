"""Safe execution helper for engine version probes."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Sequence

from qmatsuite.core.paths import tmp_probe_dir


def run_version_probe(
    command: Sequence[str],
    *,
    timeout: int = 10,
) -> subprocess.CompletedProcess[str] | None:
    """
    Execute a version probe command in an isolated probe directory.

    Why this exists:
    - Some binaries (notably certain QE builds) create transient files
      such as ``CRASH`` / ``input_tmp.in`` in the process CWD when invoked
      with probe flags like ``--version``.
    - Some probes may block waiting for stdin in interactive shells.

    This helper avoids polluting the caller CWD and prevents stdin hangs by:
    - running in a temporary subdirectory under ``tmp_probe_dir()``
    - binding stdin to ``DEVNULL``
    - enforcing a timeout
    """
    probe_root = tmp_probe_dir() / "engine_version"
    probe_root.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix="probe-", dir=str(probe_root)) as probe_cwd:
            return subprocess.run(
                list(command),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                stdin=subprocess.DEVNULL,
                cwd=probe_cwd,
            )
    except Exception:
        return None
