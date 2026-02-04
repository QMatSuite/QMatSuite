"""Yambo engine driver.

Implements the 7-item MUST interface for the Yambo MBPT engine.
Yambo is a postprocessing engine that computes GW quasiparticle
corrections, BSE optical spectra, and IP/RPA/TDDFT optics from
DFT wavefunctions (QE via p2y converter).
"""

from __future__ import annotations

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    ErrorClass,
    StepTypeSpec,
    WorkdirPolicy,
)


class YamboDriver(BaseEngineDriver):
    """Driver for the Yambo MBPT engine.

    Recipe archetype: ISOLATED workdir with shared SAVE symlink.
    Each step gets its own working directory. The setup step creates
    the SAVE/ database, and subsequent steps symlink to it.
    """

    PREFIX: str = "yambo"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "setup", "gw", "bse", "optics",
    })

    # -- MUST: Properties ---------------------------------------------------

    @property
    def engine_family(self) -> str:
        return "yambo"

    @property
    def display_name(self) -> str:
        return "Yambo"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # -- MUST: Methods ------------------------------------------------------

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        return [
            StepTypeSpec(
                step_type_spec="yambo_setup",
                engine="yambo",
                executable="yambo",
                description="Yambo setup (p2y conversion + database initialization)",
                category="postprocess",
                supports_restart=False,
                mpi_aware=False,
            ),
            StepTypeSpec(
                step_type_spec="yambo_gw",
                engine="yambo",
                executable="yambo",
                description="G0W0 quasiparticle calculation",
                category="postprocess",
                supports_restart=True,
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="yambo_bse",
                engine="yambo",
                executable="yambo",
                description="BSE optical absorption spectrum",
                category="postprocess",
                supports_restart=True,
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="yambo_optics",
                engine="yambo",
                executable="yambo",
                description="IP/RPA/TDDFT optical properties",
                category="postprocess",
                supports_restart=True,
                mpi_aware=True,
            ),
        ]

    def get_handler(self):
        from .handler import yambo_step_handler
        return yambo_step_handler

    def get_recipe_class(self):
        from .recipe import YamboRecipe
        return YamboRecipe

    # -- SHOULD: Overrides --------------------------------------------------

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        return {"gw", "bse", "optics", "postprocess", "cross_engine", "periodic"}

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        return True

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        if exit_code == 139:
            return ErrorClass.MEMORY  # Segfault (often BLAS issue)
        lower = stderr.lower()
        if "missing all or part of pp/em1s db" in lower:
            return ErrorClass.MISSING_FILE
        if "stop" in lower:
            return ErrorClass.INPUT_ERROR
        if "not found" in lower or "cannot open" in lower:
            return ErrorClass.MISSING_FILE
        if "memory" in lower or "allocation" in lower:
            return ErrorClass.MEMORY
        return ErrorClass.UNKNOWN

    def get_artifact_patterns(self) -> dict[str, str]:
        return {
            "yambo_save": "SAVE/ns.db1",
            "yambo_qp": "*/ndb.QP",
            "yambo_qp_text": "*/o-*.qp",
            "yambo_eps": "*/o-*.eps_*",
            "yambo_report": "*/r-*",
            "yambo_em1s": "*/ndb.em1s",
        }
