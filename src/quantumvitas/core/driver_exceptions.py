"""Exception classes for driver/routing errors."""

from typing import List, Optional


class DriverError(Exception):
    """Base class for driver-related errors."""
    pass


class UnknownStepTypeError(DriverError):
    """Raised when step type is not registered."""

    def __init__(self, step_type: str, known_types: Optional[List[str]] = None):
        self.step_type_spec = step_type
        self.known_types = known_types or []
        similar = self._find_similar()

        msg = f"Step type '{step_type}' is not registered."
        if similar:
            msg += f"\nDid you mean: {', '.join(similar[:3])}?"
        if self.known_types:
            preview = sorted(self.known_types)[:20]
            msg += f"\nKnown types: {', '.join(preview)}"
            if len(self.known_types) > 20:
                msg += f"... ({len(self.known_types) - 20} more)"
        super().__init__(msg)

    def _find_similar(self, max_distance: int = 3) -> List[str]:
        """Find similar type names using Levenshtein distance."""
        if not self.known_types:
            return []

        def levenshtein(s1: str, s2: str) -> int:
            if len(s1) < len(s2):
                return levenshtein(s2, s1)
            if len(s2) == 0:
                return len(s1)
            prev_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                curr_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = prev_row[j + 1] + 1
                    deletions = curr_row[j] + 1
                    substitutions = prev_row[j] + (c1 != c2)
                    curr_row.append(min(insertions, deletions, substitutions))
                prev_row = curr_row
            return prev_row[-1]

        candidates = []
        for known in self.known_types:
            dist = levenshtein(self.step_type_spec.lower(), known.lower())
            if dist <= max_distance:
                candidates.append((dist, known))

        candidates.sort(key=lambda x: x[0])
        return [c[1] for c in candidates]


class UnknownEngineError(DriverError):
    """Raised when engine family is not registered."""

    def __init__(self, engine: str, available: Optional[List[str]] = None):
        self.engine = engine
        self.available = available or []
        msg = f"No driver registered for engine '{engine}'."
        if self.available:
            msg += f"\nAvailable engines: {', '.join(sorted(self.available))}"
        super().__init__(msg)


class UnknownMaterializationError(DriverError):
    """Raised when GEN→SPEC mapping not found."""

    def __init__(
        self,
        engine: str,
        gen_type: str,
        known_gen_types: Optional[List[str]] = None,
    ):
        self.engine = engine
        self.gen_type = gen_type
        msg = f"No materialization for ({engine}, {gen_type})."
        if known_gen_types:
            msg += f"\nKnown generalized types for {engine}: {', '.join(known_gen_types)}"
        super().__init__(msg)


class InvalidDriverError(DriverError):
    """Raised when driver doesn't implement required interface."""
    pass


class DuplicateEngineError(DriverError):
    """Raised when engine family is already registered."""
    pass


class DuplicateStepTypeError(DriverError):
    """Raised when step type is already registered."""
    pass


class InvalidVersionError(DriverError):
    """Raised when driver version format is invalid."""
    pass


class IncompatibleDriverError(DriverError):
    """Raised when driver API version is incompatible with kernel."""
    pass


class NoStepTypesError(DriverError):
    """Raised when driver declares no step types."""
    pass


class EnginesMismatchError(DriverError):
    """Raised when step type's engine doesn't match driver."""
    pass

