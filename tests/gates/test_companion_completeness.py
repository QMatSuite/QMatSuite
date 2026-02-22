"""
Gate: Laws EF3/EF9 — Companion Completeness.

1. Every engine in a base engine's COMPANION_ENGINES must have ENGINE_ROLE="postprocessing".
2. Every postprocessing engine must appear in at least one base engine's COMPANION_ENGINES.
3. COMPANION_ENGINES must be a frozenset.
"""
import pytest

def test_companion_engines_are_postprocessing():
    """Every engine listed in COMPANION_ENGINES must have ENGINE_ROLE='postprocessing'."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    violations = []
    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
        for c in companions:
            if not DriverRegistry.is_engine_registered(c):
                violations.append(f"  {engine_family}.COMPANION_ENGINES references unregistered engine '{c}'")
                continue
            c_driver = DriverRegistry.get_driver(c)
            c_role = getattr(c_driver, 'ENGINE_ROLE', 'base')
            if c_role != 'postprocessing':
                violations.append(f"  {engine_family}.COMPANION_ENGINES includes '{c}' which has ENGINE_ROLE='{c_role}', not 'postprocessing'")

    assert not violations, f"EF3 violation:\n" + "\n".join(violations)


def test_every_postproc_engine_has_a_host():
    """Every postprocessing engine appears in at least one base engine's COMPANION_ENGINES."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    postproc_engines = set()
    hosted_engines = set()

    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        role = getattr(driver, 'ENGINE_ROLE', 'base')
        if role == 'postprocessing':
            postproc_engines.add(engine_family)
        companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
        hosted_engines.update(companions)

    orphans = postproc_engines - hosted_engines
    assert not orphans, f"EF9 violation — postproc engines not hosted by any base engine: {orphans}"


def test_companion_engines_is_frozenset():
    """COMPANION_ENGINES must be a frozenset on all drivers."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    violations = []
    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        companions = getattr(driver, 'COMPANION_ENGINES', None)
        if companions is None:
            violations.append(f"  {engine_family}: missing COMPANION_ENGINES")
        elif not isinstance(companions, frozenset):
            violations.append(f"  {engine_family}: COMPANION_ENGINES is {type(companions).__name__}, not frozenset")

    assert not violations, f"Type violation:\n" + "\n".join(violations)


def test_engine_role_is_valid():
    """ENGINE_ROLE must be 'base' or 'postprocessing' on all drivers."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    violations = []
    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        role = getattr(driver, 'ENGINE_ROLE', None)
        if role is None:
            violations.append(f"  {engine_family}: missing ENGINE_ROLE")
        elif role not in ('base', 'postprocessing'):
            violations.append(f"  {engine_family}: ENGINE_ROLE='{role}', must be 'base' or 'postprocessing'")

    assert not violations, f"Role violation:\n" + "\n".join(violations)



