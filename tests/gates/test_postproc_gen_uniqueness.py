"""
Gate: Law EF8 — Postprocessing Gen Step Global Uniqueness.

Every postprocessing engine's gen step names must be globally unique:
- No gen step name appears in >1 postprocessing engine's SUPPORTED_GEN_STEPS.
- No postprocessing gen step name appears in any base engine's SUPPORTED_GEN_STEPS.
"""
import pytest

def test_postproc_gen_steps_unique_across_postproc_engines():
    """No postprocessing gen step appears in more than one postproc engine."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    postproc_engines = []
    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        if getattr(driver, 'ENGINE_ROLE', 'base') == 'postprocessing':
            postproc_engines.append((engine_family, driver.SUPPORTED_GEN_STEPS))

    seen = {}  # gen_step -> engine_family
    collisions = []
    for engine_family, gen_steps in postproc_engines:
        for g in gen_steps:
            if g in seen:
                collisions.append(f"  gen step '{g}' appears in both '{seen[g]}' and '{engine_family}'")
            else:
                seen[g] = engine_family

    assert not collisions, f"EF8 violation — postproc gen step collisions:\n" + "\n".join(collisions)


def test_postproc_gen_steps_not_in_base_engines():
    """No postprocessing gen step appears in any base engine's SUPPORTED_GEN_STEPS."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    postproc_gen_steps = set()
    base_gen_steps = {}  # gen_step -> [engine_families]

    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        role = getattr(driver, 'ENGINE_ROLE', 'base')
        if role == 'postprocessing':
            postproc_gen_steps.update(driver.SUPPORTED_GEN_STEPS)
        else:
            for g in driver.SUPPORTED_GEN_STEPS:
                base_gen_steps.setdefault(g, []).append(engine_family)

    collisions = []
    for g in postproc_gen_steps:
        if g in base_gen_steps:
            collisions.append(f"  postproc gen step '{g}' also in base engines: {base_gen_steps[g]}")

    assert not collisions, f"EF8 violation — postproc/base gen step overlap:\n" + "\n".join(collisions)



