"""Registry, collection, feature assembly, the model runner, and calibration.

Everything here operates on models and collectors without knowing what any of them
do. The two tiers meet in exactly one place: a collector declares the signal paths
it provides, and a model declares the paths it requires.
"""

from .calibration import CalibrationResult, CohortInfo, calibrate, resolve_cohort
from .collectors import (
    CollectionRun,
    CollectorOutcome,
    CollectorRegistrationError,
    CollectorRegistry,
    apply_signals,
    run_collectors,
)
from .join import expand_paths, join_values, merge_signals, signal_path
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
    "CollectionRun",
    "CollectorOutcome",
    "CollectorRegistrationError",
    "CollectorRegistry",
    "RegisteredModel",
    "RegistrationError",
    "Registry",
    "RunResult",
    "Skip",
    "apply_signals",
    "build_registry",
    "calibrate",
    "contracts_dir",
    "data_dir",
    "expand_paths",
    "fixtures_dir",
    "join_values",
    "merge_signals",
    "repo_root",
    "resolve_cohort",
    "run_collectors",
    "run_models",
    "schemas_dir",
    "signal_path",
    "snapshot_feature_paths",
]
