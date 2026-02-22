"""
API DTO types.

This module exports all Data Transfer Objects (DTOs) for the API.
"""

from qmatsuite.api.types.analysis import AnalysisRefDTO, AnalysisSummaryDTO
from qmatsuite.api.types.base import BaseDTO, JsonValue, to_json_value
from qmatsuite.api.types.calculation import CalculationDTO, CalculationRefDTO, StepDTO
from qmatsuite.api.types.common import MetaDTO, CandidateSummary
from qmatsuite.api.types.error import ErrorDTO
from qmatsuite.api.types.run import RunResultDTO
from qmatsuite.api.types.structure import StructureDTO

__all__ = [
    # Base
    "BaseDTO",
    "JsonValue",
    "to_json_value",
    # Common
    "MetaDTO",
    "CandidateSummary",
    # Error
    "ErrorDTO",
    # Calculation
    "CalculationDTO",
    "CalculationRefDTO",
    "StepDTO",
    # Structure
    "StructureDTO",
    # Run
    "RunResultDTO",
    # Analysis
    "AnalysisRefDTO",
    "AnalysisSummaryDTO",
]
