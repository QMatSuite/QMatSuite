"""Driver registry for engine-to-driver mapping.

This module provides the central registry that maps:
- Engine families to driver instances
- Step types to their specifications
- Generalized types to engine-specific types

The registry is a singleton that drivers register with at import time.
"""

from __future__ import annotations

import logging
from threading import Lock
from typing import TYPE_CHECKING, Callable

from qmatsuite.core.driver_exceptions import (
    DuplicateEngineError,
    DuplicateStepTypeError,
    EnginesMismatchError,
    IncompatibleDriverError,
    InvalidDriverError,
    InvalidVersionError,
    NoStepTypesError,
    UnknownEngineError,
    UnknownMaterializationError,
    UnknownStepTypeError,
)
from qmatsuite.core.driver_protocol import EngineDriver, StepTypeSpec
from qmatsuite.core.step_type_convert import spec_from

if TYPE_CHECKING:
    from qmatsuite.execution.job_graph import Job
    from qmatsuite.execution.executor import JobResult

logger = logging.getLogger(__name__)

# Current kernel API version
KERNEL_API_VERSION = "1.0.0"


class DriverRegistry:
    """Singleton registry for engine drivers.

    Usage:
        # Registration (at driver import time)
        DriverRegistry.register(MyEngineDriver())

        # Lookup
        driver = DriverRegistry.get_driver("vasp")
        handler = DriverRegistry.get_handler("vasp_scf")
        spec = DriverRegistry.get_step_type_spec("vasp_scf")
    """

    _instance: DriverRegistry | None = None
    _lock = Lock()

    def __new__(cls) -> DriverRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize registry state."""
        self._drivers: dict[str, EngineDriver] = {}
        self._step_types: dict[str, StepTypeSpec] = {}
        self._step_to_engine: dict[str, str] = {}
        self._materialization_maps: dict[str, dict[str, str]] = {}
        self._frozen = False

    @classmethod
    def get_instance(cls) -> DriverRegistry:
        """Get the singleton registry instance."""
        return cls()

    @classmethod
    def register(cls, driver: EngineDriver) -> None:
        """Register a driver with the registry.

        Args:
            driver: Driver instance implementing EngineDriver protocol

        Raises:
            InvalidDriverError: If driver doesn't implement required interface
            DuplicateEngineError: If engine family already registered
            InvalidVersionError: If version format is invalid
            IncompatibleDriverError: If API version incompatible
            NoStepTypesError: If driver declares no step types
            DuplicateStepTypeError: If step type already registered
            EnginesMismatchError: If step type engine doesn't match driver
        """
        instance = cls.get_instance()
        instance._register(driver)

    def _register(self, driver: EngineDriver) -> None:
        """Internal registration logic."""
        if self._frozen:
            raise RuntimeError("Registry is frozen, cannot register new drivers")

        # Validate driver implements protocol
        self._validate_driver(driver)

        family = driver.engine_family

        # Check for duplicate registration
        if family in self._drivers:
            raise DuplicateEngineError(
                f"Engine '{family}' already registered by {type(self._drivers[family]).__name__}"
            )

        # Register driver
        self._drivers[family] = driver
        logger.info(f"Registered driver: {driver.display_name} ({family})")

        # Register step types (use step_type_spec as key - unique per engine)
        for spec in driver.get_step_type_specs():
            if spec.step_type_spec in self._step_types:
                raise DuplicateStepTypeError(
                    f"Step type '{spec.step_type_spec}' already registered by engine "
                    f"'{self._step_to_engine[spec.step_type_spec]}'"
                )
            self._step_types[spec.step_type_spec] = spec
            self._step_to_engine[spec.step_type_spec] = family
            logger.debug(f"  Registered step type: {spec.step_type_spec}")

        # Register materialization map
        # Build from PREFIX + SUPPORTED_GEN_STEPS if available, otherwise use get_materialization_map()
        mat_map = self._build_materialization_map(driver)
        if mat_map:
            self._materialization_maps[family] = mat_map
            logger.debug(f"  Registered {len(mat_map)} materialization mappings")

    def _validate_driver(self, driver: EngineDriver) -> None:
        """Validate driver conforms to protocol."""
        # Check required properties
        family = driver.engine_family
        if not family or not isinstance(family, str):
            raise InvalidDriverError("engine_family must be non-empty string")

        if not family.replace("_", "").isalnum() or not family.islower():
            raise InvalidDriverError(
                f"engine_family '{family}' must be lowercase alphanumeric with underscores"
            )

        display = driver.display_name
        if not display or not isinstance(display, str):
            raise InvalidDriverError("display_name must be non-empty string")

        # Validate version
        version = driver.driver_api_version
        try:
            parts = version.split(".")
            if len(parts) != 3:
                raise ValueError("Must have 3 parts")
            major, minor, patch = map(int, parts)
        except (ValueError, AttributeError) as e:
            raise InvalidVersionError(f"Invalid version format '{version}': {e}")

        # Check API compatibility
        kernel_major = int(KERNEL_API_VERSION.split(".")[0])
        if major != kernel_major:
            raise IncompatibleDriverError(
                f"Driver requires API v{major}.x but kernel supports v{kernel_major}.x"
            )

        # Validate step types
        specs = driver.get_step_type_specs()
        if not specs:
            raise NoStepTypesError(f"Driver {family} declares no step types")

        for spec in specs:
            if spec.engine != family:
                raise EnginesMismatchError(
                    f"Step type '{spec.step_type_spec}' declares engine '{spec.engine}' "
                    f"but driver is '{family}'"
                )

    def _build_materialization_map(self, driver: EngineDriver) -> dict[str, str]:
        """Build materialization map from PREFIX + SUPPORTED_GEN_STEPS.
        
        Pure derivation only: {gen: f"{PREFIX}_{gen}"} for supported gens.
        No exceptions, no special cases, no overrides.
        
        Args:
            driver: Driver instance
            
        Returns:
            Materialization map: {gen: spec_type} where spec_type = f"{prefix}_{gen}"
        """
        mat_map: dict[str, str] = {}
        
        # Build from PREFIX + SUPPORTED_GEN_STEPS if available
        if hasattr(driver, 'PREFIX') and hasattr(driver, 'SUPPORTED_GEN_STEPS'):
            prefix = driver.PREFIX
            supported_gen_steps = driver.SUPPORTED_GEN_STEPS
            for gen_step in supported_gen_steps:
                # Pure derivation: gen (lowercase) → spec = f"{prefix}_{gen}"
                spec_type = spec_from(prefix, gen_step)
                mat_map[gen_step] = spec_type
        
        return mat_map

    @classmethod
    def get_driver(cls, engine_family: str) -> EngineDriver:
        """Get driver by engine family.

        Args:
            engine_family: Engine identifier (e.g., 'vasp')

        Returns:
            Driver instance

        Raises:
            UnknownEngineError: If engine not registered
        """
        instance = cls.get_instance()
        if engine_family not in instance._drivers:
            raise UnknownEngineError(engine_family, list(instance._drivers.keys()))
        return instance._drivers[engine_family]

    @classmethod
    def get_handler(cls, step_type_spec: str) -> Callable[["Job", dict[str, Any]], "JobResult"]:
        """Get handler for step type.

        Args:
            step_type_spec: Spec step type identifier (e.g., 'vasp_scf', 'qe_scf')

        Returns:
            Handler function

        Raises:
            UnknownStepTypeError: If step type not registered
        """
        instance = cls.get_instance()
        if step_type_spec not in instance._step_to_engine:
            raise UnknownStepTypeError(step_type_spec, list(instance._step_types.keys()))

        engine = instance._step_to_engine[step_type_spec]
        driver = instance._drivers[engine]
        return driver.get_handler()

    @classmethod
    def get_recipe_class(cls, engine_family: str) -> type:
        """Get recipe class for engine.

        Args:
            engine_family: Engine identifier (e.g., 'vasp')

        Returns:
            Recipe class

        Raises:
            UnknownEngineError: If engine not registered
        """
        driver = cls.get_driver(engine_family)
        return driver.get_recipe_class()

    @classmethod
    def get_step_type_spec(cls, step_type_spec: str) -> StepTypeSpec:
        """Get specification for step type.

        Args:
            step_type_spec: Spec step type identifier (e.g., 'vasp_scf', 'qe_scf')

        Returns:
            StepTypeSpec instance

        Raises:
            UnknownStepTypeError: If step type not registered
        """
        instance = cls.get_instance()
        if step_type_spec not in instance._step_types:
            raise UnknownStepTypeError(step_type_spec, list(instance._step_types.keys()))
        return instance._step_types[step_type_spec]

    @classmethod
    def get_engine_for_step_type(cls, step_type_spec: str) -> str:
        """Get engine family for step type.

        Args:
            step_type_spec: Spec step type identifier (e.g., 'vasp_scf', 'qe_scf')

        Returns:
            Engine family string

        Raises:
            UnknownStepTypeError: If step type not registered
        """
        instance = cls.get_instance()
        if step_type_spec not in instance._step_to_engine:
            raise UnknownStepTypeError(step_type_spec, list(instance._step_types.keys()))
        return instance._step_to_engine[step_type_spec]

    @classmethod
    def materialize_step_type(cls, engine_family: str, gen_type: str) -> str:
        """Materialize generalized type to engine-specific type.

        Args:
            engine_family: Engine identifier (e.g., 'vasp')
            gen_type: Generalized type (e.g., 'scf') - lowercase gen step name, NOT GEN_* format

        Returns:
            Engine-specific step type (e.g., 'vasp_scf')

        Raises:
            UnknownEngineError: If engine not registered
            UnknownMaterializationError: If no mapping exists
        """
        instance = cls.get_instance()

        if engine_family not in instance._drivers:
            raise UnknownEngineError(engine_family, list(instance._drivers.keys()))

        # Normalize gen_type to lowercase (remove GEN_ prefix if present for backward compat during migration)
        gen_type_lower = gen_type.lower()
        if gen_type_lower.startswith("gen_"):
            gen_type_lower = gen_type_lower[4:]

        mat_map = instance._materialization_maps.get(engine_family, {})
        if gen_type_lower not in mat_map:
            raise UnknownMaterializationError(
                engine_family, gen_type_lower, list(mat_map.keys())
            )

        return mat_map[gen_type_lower]

    @classmethod
    def resolve_companion_step(cls, engine_family: str, gen_step: str) -> str | None:
        """Resolve a gen step through companion engines.

        Tries the base engine first, then iterates COMPANION_ENGINES.

        Args:
            engine_family: Base engine family (e.g., 'qe')
            gen_step: Generalized step name (e.g., 'wannierprep')

        Returns:
            Engine-specific step type (e.g., 'w90_wannierprep'), or None if
            not supported by base engine or any companion.
        """
        instance = cls.get_instance()

        if engine_family not in instance._drivers:
            from qmatsuite.core.driver_exceptions import UnknownEngineError
            raise UnknownEngineError(engine_family, list(instance._drivers.keys()))

        gen_lower = gen_step.lower()
        if gen_lower.startswith("gen_"):
            gen_lower = gen_lower[4:]

        # 1. Try base engine
        mat_map = instance._materialization_maps.get(engine_family, {})
        if gen_lower in mat_map:
            return mat_map[gen_lower]

        # 2. Try each companion engine
        driver = instance._drivers[engine_family]
        companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
        for companion in sorted(companions):  # sorted for determinism
            comp_map = instance._materialization_maps.get(companion, {})
            if gen_lower in comp_map:
                return comp_map[gen_lower]

        return None

    @classmethod
    def is_step_type_registered(cls, step_type_spec: str) -> bool:
        """Check if step type is registered."""
        instance = cls.get_instance()
        return step_type_spec in instance._step_types

    @classmethod
    def is_engine_registered(cls, engine_family: str) -> bool:
        """Check if engine is registered."""
        instance = cls.get_instance()
        return engine_family in instance._drivers

    @classmethod
    def get_all_step_types(cls) -> list[str]:
        """Get all registered step type IDs."""
        instance = cls.get_instance()
        return list(instance._step_types.keys())

    @classmethod
    def get_all_engines(cls) -> list[str]:
        """Get all registered engine families."""
        instance = cls.get_instance()
        return list(instance._drivers.keys())

    @classmethod
    def get_step_types_for_engine(cls, engine_family: str) -> list[str]:
        """Get all step types for an engine."""
        instance = cls.get_instance()
        return [
            st for st, eng in instance._step_to_engine.items()
            if eng == engine_family
        ]

    @classmethod
    def freeze(cls) -> None:
        """Freeze registry to prevent further registrations.

        Call after all drivers are loaded to catch late registrations.
        """
        instance = cls.get_instance()
        instance._frozen = True
        logger.info(
            f"Registry frozen: {len(instance._drivers)} engines, "
            f"{len(instance._step_types)} step types"
        )

    @classmethod
    def reset(cls) -> None:
        """Reset registry for testing purposes only.

        WARNING: Only use in tests. Never call in production code.
        """
        instance = cls.get_instance()
        instance._initialize()
        logger.warning("Registry reset - this should only happen in tests")

