"""WMIT MSK Simulation Engine.

OpenSim 기반 근골격 해석 파이프라인. 웹 계층에 의존하지 않는다.
"""

__version__ = "0.1.0"

from msk_engine.errors import (
    InputValidationError,
    MskEngineError,
    StepExecutionError,
)

__all__ = [
    "__version__",
    "MskEngineError",
    "InputValidationError",
    "StepExecutionError",
]
