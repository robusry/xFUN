"""The model registry.

Registration is where a model's declarations are checked against reality. In
particular, a model that declares a feature the snapshot schema does not define is
rejected here rather than silently skipping every match at runtime -- a typo in
`required_features` should be a loud registration error, not a model that quietly
never scores anything.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from xfun_contract import Model

from .paths import schemas_dir

__all__ = ["Registry", "RegisteredModel", "RegistrationError", "snapshot_feature_paths"]

_ID_PATTERN = re.compile(r"^[a-z0-9-]+$")
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


class RegistrationError(Exception):
    """A model's declarations are inconsistent with the contract."""


@dataclass(frozen=True)
class RegisteredModel:
    model: Model
    retired: bool = False

    @property
    def model_id(self) -> str:
        return self.model.model_id

    @property
    def model_version(self) -> str:
        return self.model.model_version


def snapshot_feature_paths() -> frozenset[str]:
    """Every dotted path the snapshot schema defines.

    Derived from contracts/schemas/match-snapshot.json rather than hand-maintained,
    so the schema stays the single source of truth for what a model may ask for.
    """
    schema = json.loads((schemas_dir() / "match-snapshot.json").read_text())
    defs = schema.get("$defs", {})
    found: set[str] = set()

    def resolve(node: Mapping[str, Any]) -> Mapping[str, Any]:
        ref = node.get("$ref")
        if ref and ref.startswith("#/$defs/"):
            return defs.get(ref.split("/")[-1], {})
        return node

    def walk(node: Mapping[str, Any], prefix: str, depth: int = 0) -> None:
        if depth > 10:  # guards against a cyclic $ref
            return
        node = resolve(node)
        for name, child in (node.get("properties") or {}).items():
            path = f"{prefix}.{name}" if prefix else name
            found.add(path)
            walk(child, path, depth + 1)

    walk(schema, "")
    return frozenset(found)


class Registry:
    """Holds the models a scoring run will fan out over."""

    def __init__(self, *, validate_features: bool = True) -> None:
        self._models: dict[str, RegisteredModel] = {}
        self._validate_features = validate_features
        self._known_paths = snapshot_feature_paths() if validate_features else frozenset()

    def register(self, model: Model, *, retired: bool = False) -> None:
        if not _ID_PATTERN.match(model.model_id):
            raise RegistrationError(
                f"model_id {model.model_id!r} must be kebab-case: [a-z0-9-]+"
            )
        if not _VERSION_PATTERN.match(model.model_version):
            raise RegistrationError(
                f"{model.model_id}: model_version {model.model_version!r} must be semver"
            )
        if model.model_id in self._models:
            raise RegistrationError(f"model_id {model.model_id!r} is already registered")
        if not model.required_features:
            raise RegistrationError(
                f"{model.model_id}: must declare at least one required feature"
            )

        if self._validate_features:
            unknown = sorted(set(model.required_features) - self._known_paths)
            if unknown:
                raise RegistrationError(
                    f"{model.model_id}: declares features absent from "
                    f"match-snapshot.json: {', '.join(unknown)}"
                )

        self._models[model.model_id] = RegisteredModel(model=model, retired=retired)

    def active(self) -> tuple[RegisteredModel, ...]:
        """Models that produce new scores. Retired models are excluded here but
        their historical rows remain queryable."""
        return tuple(m for m in self._models.values() if not m.retired)

    def all(self) -> tuple[RegisteredModel, ...]:
        return tuple(self._models.values())

    def get(self, model_id: str) -> RegisteredModel | None:
        return self._models.get(model_id)

    def __len__(self) -> int:
        return len(self._models)

    def __contains__(self, model_id: object) -> bool:
        return model_id in self._models


def build_registry(models: Iterable[Model]) -> Registry:
    registry = Registry()
    for model in models:
        registry.register(model)
    return registry
