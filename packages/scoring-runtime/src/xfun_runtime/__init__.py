"""Registry, feature assembly, the model runner, and calibration.

Everything here operates on models without knowing what any of them do.
"""

from .calibration import CalibrationResult, CohortInfo, calibrate, resolve_cohort
from .paths import contracts_dir, data_dir, fixtures_dir, repo_root, schemas_dir
from .registry import (
    RegisteredModel,
    RegistrationError,
    Registry,
    build_registry,
    snapshot_feature_paths,
)
from .runner import RunResult, Skip, run_models

__all__ = [
    "CalibrationResult",
    "CohortInfo",
    "RegisteredModel",
    "RegistrationError",
    "Registry",
    "RunResult",
    "Skip",
    "build_registry",
    "calibrate",
    "contracts_dir",
    "data_dir",
    "fixtures_dir",
    "repo_root",
    "resolve_cohort",
    "run_models",
    "schemas_dir",
    "snapshot_feature_paths",
]
