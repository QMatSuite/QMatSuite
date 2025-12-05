"""
Quantum ESPRESSO installation detection and path management.

This module provides utilities to automatically detect QE installation
by storing the QE home directory (which contains bin/ and test-suite/).

The detected QE home is stored in an internal registry (not os.environ)
to avoid pollution from external processes. Use get_qe_home()/set_qe_home()
to access or modify the configured path.
"""

from pathlib import Path
from typing import Optional
import os
import shutil
import re


# ============================================================================
# Module-level QE Home Registry
# ============================================================================
# Internal storage for QE home path - NOT stored in os.environ to prevent
# pollution from external processes or test isolation issues.

_qe_home_registry: Optional[Path] = None
_qe_home_initialized: bool = False


def get_qe_home() -> Optional[Path]:
    """
    Get the currently configured QE home directory.
    
    Returns the internal registry value (not os.environ["QE_HOME"]).
    If not yet initialized, triggers auto-detection.
    
    Returns:
        Path to QE home directory, or None if not found/configured.
    """
    global _qe_home_registry, _qe_home_initialized
    
    if not _qe_home_initialized:
        # First access - initialize from environment or auto-detect
        _initialize_qe_home()
    
    return _qe_home_registry


def set_qe_home(path: Optional[Path]) -> None:
    """
    Explicitly set the QE home directory.
    
    Use this to override auto-detection or configure QE programmatically.
    Does NOT modify os.environ["QE_HOME"].
    
    Args:
        path: Path to QE home directory (must contain bin/pw.x), or None to clear.
        
    Raises:
        ValueError: If path is provided but invalid (no bin/pw.x).
    """
    global _qe_home_registry, _qe_home_initialized
    
    if path is not None:
        path = Path(path).expanduser()
        try:
            path = path.resolve()
        except OSError:
            pass
        if not QEInstallation._validate_qe_home(path):
            raise ValueError(f"Invalid QE home directory: {path}. Must contain bin/pw.x")
    
    _qe_home_registry = path
    _qe_home_initialized = True


def reset_qe_home() -> None:
    """
    Reset the QE home registry to uninitialized state.
    
    Next call to get_qe_home() will re-run auto-detection.
    Useful for testing or when QE installation changes.
    """
    global _qe_home_registry, _qe_home_initialized
    _qe_home_registry = None
    _qe_home_initialized = False


def _initialize_qe_home() -> None:
    """
    Initialize QE home from environment variable or auto-detection.
    
    Called automatically on first access to get_qe_home().
    Reads QE_HOME from os.environ once, then stores internally.
    """
    global _qe_home_registry, _qe_home_initialized
    
    _qe_home_initialized = True
    
    # Read from environment variable (one-time read)
    qe_home_env = os.environ.get("QE_HOME")
    if qe_home_env:
        try:
            path = Path(qe_home_env).expanduser().resolve()
            if QEInstallation._validate_qe_home(path):
                _qe_home_registry = path
                return
        except OSError:
            pass
    
    # Auto-detect using QEInstallation strategies
    detected = QEInstallation._detect_qe_home()
    if detected:
        _qe_home_registry = detected


class QEInstallation:
    """
    Represents a Quantum ESPRESSO installation with automatic path detection.
    
    Stores QE home directory (contains bin/ and test-suite/).
    Automatically detects from:
    1. User-provided path (validated: must have bin/pw.x)
    2. QE_HOME environment variable
    3. System PATH (using which pw.x, then finding QE home)
    4. Shell config files (~/.zshrc, ~/.zprofile, ~/.zshenv, ~/.bashrc, ~/.bash_profile, ~/.profile)
    5. Default location: $HOME/src/q-e-qe-7.5
    """
    
    def __init__(self, qe_home: Optional[Path] = None):
        """
        Initialize QE installation detector.
        
        Args:
            qe_home: Optional explicit path to QE home directory.
                    If None, will use the module registry (auto-detected or set via set_qe_home()).
        """
        self._qe_home: Optional[Path] = None
        
        if qe_home:
            # User provided explicit path - validate and use it
            explicit_home = Path(qe_home).expanduser()
            try:
                resolved = explicit_home.resolve()
            except OSError:
                resolved = explicit_home
            if self._validate_qe_home(resolved):
                self._qe_home = resolved
                # Also update the module registry so other code sees this
                set_qe_home(resolved)
            else:
                raise ValueError(f"Invalid QE home directory: {qe_home}. Must contain bin/pw.x")
        else:
            # Use the module-level registry (triggers auto-detection if needed)
            self._qe_home = get_qe_home()
    
    @staticmethod
    def _validate_qe_home(qe_home: Path) -> bool:
        """
        Validate that a path is a valid QE home directory.
        
        Args:
            qe_home: Path to check
            
        Returns:
            True if valid (contains bin/pw.x), False otherwise
        """
        if not qe_home.exists() or not qe_home.is_dir():
            return False
        
        pw_x = qe_home / "bin" / "pw.x"
        return pw_x.exists() and pw_x.is_file()
    
    @staticmethod
    def qe_home_from_binary(executable_path: Path) -> Optional[Path]:
        """
        Infer QE home directory from an executable path.

        Args:
            executable_path: Path pointing to pw.x/ph.x/etc inside bin/

        Returns:
            Path to QE home if the executable lives under <qe_home>/bin.
        """
        path = Path(executable_path).expanduser()
        if not path.exists():
            return None

        try:
            path = path.resolve()
        except OSError:
            pass

        bin_dir = path.parent
        if bin_dir.name != "bin":
            return None

        qe_home = bin_dir.parent
        if QEInstallation._validate_qe_home(qe_home):
            return qe_home
        return None

    @staticmethod
    def _detect_qe_home() -> Optional[Path]:
        """
        Automatically detect QE home directory using heuristics.
        
        Note: This does NOT check os.environ["QE_HOME"] - that's handled
        separately by _initialize_qe_home() to ensure the env var is only
        read once at startup.
        
        Search order:
        1. System PATH (using which pw.x/ph.x and inferring QE_HOME)
        2. Shell configuration files (e.g., ~/.zshrc, ~/.bashrc) for local dev
        3. Home directory scan (q-e-qe*, quantum-espresso, etc.)
        
        Returns:
            Path to QE home directory if found, None otherwise
        """
        # Strategy 1: System PATH (using which pw.x)
        for exe_name in ("pw.x", "ph.x"):
            exe_path = shutil.which(exe_name)
            if exe_path:
                qe_home = QEInstallation.qe_home_from_binary(Path(exe_path))
                if qe_home:
                    return qe_home
        
        # Strategy 2: Shell configuration files (for local development)
        shell_qe_home = QEInstallation._extract_from_shell_config()
        if shell_qe_home:
            return shell_qe_home
        
        # Strategy 3: Search in home directory (max 3 levels deep)
        home_dir = Path.home()
        candidates = []
        
        # First pass: prioritize q-e-qe* folders
        try:
            for level1 in home_dir.iterdir():
                if not level1.is_dir():
                    continue
                level1_name = level1.name.lower()
                
                # Check level 1: q-e-qe* (highest priority)
                if level1_name.startswith("q-e-qe"):
                    candidates.insert(0, level1)  # Insert at beginning for priority
                
                # Check level 2 (max depth 3, so we can go 2 more levels)
                try:
                    for level2 in level1.iterdir():
                        if not level2.is_dir():
                            continue
                        level2_name = level2.name.lower()
                        
                        # Check level 2: q-e-qe*
                        if level2_name.startswith("q-e-qe"):
                            candidates.insert(0, level2)
                        
                        # Check level 3
                        try:
                            for level3 in level2.iterdir():
                                if not level3.is_dir():
                                    continue
                                level3_name = level3.name.lower()
                                
                                # Check level 3: q-e-qe*
                                if level3_name.startswith("q-e-qe"):
                                    candidates.insert(0, level3)
                        except (PermissionError, OSError):
                            continue
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        
        # Second pass: find qe or quantum-espresso folders (case-insensitive)
        try:
            for level1 in home_dir.iterdir():
                if not level1.is_dir():
                    continue
                level1_name = level1.name.lower()
                
                # Check if it matches: "qe" or contains "quantum" and "espresso"
                is_qe_candidate = (
                    level1_name == "qe" or
                    ("quantum" in level1_name and "espresso" in level1_name)
                )
                
                if is_qe_candidate and level1 not in candidates:
                    candidates.append(level1)
                
                # Check level 2
                try:
                    for level2 in level1.iterdir():
                        if not level2.is_dir():
                            continue
                        level2_name = level2.name.lower()
                        
                        is_qe_candidate = (
                            level2_name == "qe" or
                            ("quantum" in level2_name and "espresso" in level2_name)
                        )
                        
                        if is_qe_candidate and level2 not in candidates:
                            candidates.append(level2)
                        
                        # Check level 3
                        try:
                            for level3 in level2.iterdir():
                                if not level3.is_dir():
                                    continue
                                level3_name = level3.name.lower()
                                
                                is_qe_candidate = (
                                    level3_name == "qe" or
                                    ("quantum" in level3_name and "espresso" in level3_name)
                                )
                                
                                if is_qe_candidate and level3 not in candidates:
                                    candidates.append(level3)
                        except (PermissionError, OSError):
                            continue
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        
        # Validate candidates in priority order
        for candidate in candidates:
            # Check if bin/pw.x exists (fully compiled)
            pw_x_path = candidate / "bin" / "pw.x"
            if pw_x_path.exists() and pw_x_path.is_file() and os.access(pw_x_path, os.X_OK):
                return candidate.resolve()
            
            # Check if pw and neb subdirectories exist (not yet compiled, but correct location)
            # Case-insensitive check
            has_pw = False
            has_neb = False
            try:
                for subdir in candidate.iterdir():
                    if not subdir.is_dir():
                        continue
                    subdir_name_lower = subdir.name.lower()
                    if subdir_name_lower == "pw":
                        has_pw = True
                    elif subdir_name_lower == "neb":
                        has_neb = True
            except (PermissionError, OSError):
                continue
            
            # If both pw and neb exist, this is likely the right location but not compiled
            # Continue searching for a compiled version
            if has_pw and has_neb:
                # This is a valid QE source directory but not compiled, continue searching
                continue
        
        if candidates:
            for candidate in candidates:
                pw_x_path = candidate / "bin" / "pw.x"
                if pw_x_path.exists():
                    qe_home = QEInstallation.qe_home_from_binary(pw_x_path)
                    if qe_home:
                        return qe_home
        
        # If no compiled version found, return None
        return None
    
    @staticmethod
    def _extract_from_shell_config() -> Optional[Path]:
        """
        Extract QE home from shell configuration files.
        
        Looks for PATH exports in common shell config files that may contain
        q-e-qe or quantum-espresso paths.
        
        Supported files (checked in order):
        - ~/.zshrc, ~/.zprofile, ~/.zshenv (zsh - macOS default)
        - ~/.bashrc, ~/.bash_profile (bash)
        - ~/.profile (generic POSIX)
        
        Returns:
            Path to QE home if found, None otherwise
        """
        # Common shell configuration files across different OS
        # macOS: zsh is default since Catalina
        # Linux: bash is common default, but zsh also used
        rc_names = [
            ".zshrc",        # zsh interactive
            ".zprofile",     # zsh login (macOS commonly uses this)
            ".zshenv",       # zsh always sourced
            ".bashrc",       # bash interactive
            ".bash_profile", # bash login
            ".profile",      # generic POSIX login
        ]
        shell_configs: list[Path] = []
        seen: set[Path] = set()

        def _add(path: Path):
            if path in seen:
                return
            seen.add(path)
            shell_configs.append(path)

        home_dir = Path.home()
        for name in rc_names:
            _add(home_dir / name)

        users_root = Path("/Users")
        if users_root.exists():
            try:
                for entry in users_root.iterdir():
                    if not entry.is_dir() or entry == home_dir:
                        continue
                    for name in rc_names:
                        _add(entry / name)
            except PermissionError:
                pass

        def _expand_candidate(value: str) -> Path:
            expanded = value.replace("$HOME", str(Path.home()))
            expanded = os.path.expandvars(expanded)
            expanded = os.path.expanduser(expanded)
            return Path(expanded)

        for config_file in shell_configs:
            if not config_file.exists():
                continue
            
            try:
                content = config_file.read_text()
            except Exception:
                continue

            # Step 1: look for explicit QE_HOME exports
            env_patterns = [
                r"export\s+QE_HOME\s*=\s*['\"]?([^'\"]+)['\"]?",
                r"QE_HOME\s*=\s*['\"]?([^'\"]+)['\"]?",
            ]
            for pattern in env_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    try:
                        candidate = _expand_candidate(match).resolve()
                    except Exception:
                        continue
                    if QEInstallation._validate_qe_home(candidate):
                        return candidate

            # Step 2: look for explicit references to pw.x/ph.x
            tokens = re.split(r'[\s"\'=]+', content)
            for token in tokens:
                if not token or "pw.x" not in token and "ph.x" not in token:
                    continue
                if "/" not in token:
                    continue
                expanded = token.replace("$HOME", str(Path.home()))
                expanded = os.path.expandvars(os.path.expanduser(expanded))
                exe_path = Path(expanded)
                qe_home = QEInstallation.qe_home_from_binary(exe_path)
                if qe_home:
                    return qe_home

            # Step 3: fallback to original PATH-based heuristics
            try:
                patterns = [
                    r'export\s+PATH=["\']([^"\']*q-e-qe[^"\']*)/bin',
                    r'export\s+PATH=["\']([^"\']*quantum-espresso[^"\']*)/bin',
                    r'PATH=["\']([^"\']*q-e-qe[^"\']*)/bin',
                    r'PATH=["\']([^"\']*quantum-espresso[^"\']*)/bin',
                ]

                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        path_str = match.replace("$HOME", str(Path.home()))
                        path_str = os.path.expandvars(os.path.expanduser(path_str))
                        candidate = Path(path_str).expanduser()
                        try:
                            candidate = candidate.resolve()
                        except OSError:
                            pass
                        if QEInstallation._validate_qe_home(candidate):
                            return candidate
            except Exception:
                continue

        return None
    
    
    @property
    def qe_home(self) -> Optional[Path]:
        """Get QE home directory (contains bin/ and test-suite/)."""
        return self._qe_home
    
    @property
    def bin_dir(self) -> Optional[Path]:
        """Get QE bin directory."""
        if self._qe_home:
            return self._qe_home / "bin"
        return None
    
    @property
    def root_dir(self) -> Optional[Path]:
        """Get QE root directory (same as qe_home)."""
        return self._qe_home
    
    @property
    def test_suite_dir(self) -> Optional[Path]:
        """Get QE test-suite directory."""
        if self._qe_home:
            test_suite = self._qe_home / "test-suite"
            if test_suite.exists() and test_suite.is_dir():
                return test_suite
        return None
    
    @property
    def pseudo_dir(self) -> Optional[Path]:
        """Get QE pseudopotential directory."""
        if not self._qe_home:
            return None
        
        # Try common locations
        possible_locations = [
            self._qe_home / "pseudo",
            self._qe_home / "test-suite" / "pseudo",
        ]
        
        for location in possible_locations:
            if location.exists() and location.is_dir():
                return location
        
        return None
    
    def is_valid(self) -> bool:
        """Check if this is a valid QE installation."""
        return self._qe_home is not None and self._validate_qe_home(self._qe_home)
    
    def find_executable(self, executable_name: str) -> Optional[Path]:
        """
        Find an executable in the bin directory.
        
        Args:
            executable_name: Name of executable (e.g., "pw.x", "ph.x")
            
        Returns:
            Path to executable if found, None otherwise
        """
        if not self._qe_home:
            return None
        
        exe_path = self._qe_home / "bin" / executable_name
        if exe_path.exists() and exe_path.is_file():
            return exe_path
        
        return None
    
    def __repr__(self) -> str:
        """String representation."""
        return f"QEInstallation(qe_home={self._qe_home})"

