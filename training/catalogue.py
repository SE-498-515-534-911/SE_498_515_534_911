"""Model catalogue (US-06, MLE-F-007).

The catalogue is a FIXED list of classification algorithms (SRS Table 4.3-1).
The system never accepts a user-supplied model or algorithm, which removes the
unsafe-deserialisation risk described in SAD 3.7 (R3) and MLE-SR-004.

This module is pure Python: it does not import Django, so the training worker
process can import it cheaply.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class UnknownModel(KeyError):
    """Raised when a model key is not in the catalogue."""


@dataclass(frozen=True)
class ParamSpec:
    """One user-editable hyperparameter and its permitted range (SRS Table 4.3-1)."""

    name: str
    kind: str  # "int" | "float" | "choice" | "int_or_none"
    default: Any
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple = ()
    label: str = ""

    def range_text(self) -> str:
        """Plain-language description of the permitted values, used in error messages."""
        lo, hi = self.minimum, self.maximum
        if self.kind == "int":
            return f"a whole number between {lo:g} and {hi:g}"
        if self.kind == "float":
            return f"a number between {lo:g} and {hi:g}"
        if self.kind == "int_or_none":
            return f"a whole number between {lo:g} and {hi:g}, or empty for no limit"
        if self.kind == "choice":
            return "one of: " + ", ".join(self.choices)
        raise ValueError(f"unknown parameter kind {self.kind!r}")  # pragma: no cover

    def describe(self) -> dict:
        return {
            "name": self.name,
            "label": self.label or self.name,
            "kind": self.kind,
            "default": self.default,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "choices": list(self.choices),
            "range": self.range_text(),
        }


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    description: str
    estimator: str  # "module:ClassName", imported only when an estimator is built
    params: tuple[ParamSpec, ...]
    # Fixed (not user-editable) constructor arguments.
    fixed: tuple[tuple[str, Any], ...] = ()
    provides_feature_importance: bool = True

    def defaults(self) -> dict:
        return {p.name: p.default for p in self.params}

    def param(self, name: str) -> ParamSpec | None:
        return next((p for p in self.params if p.name == name), None)

    def describe(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "defaults": self.defaults(),
            "params": [p.describe() for p in self.params],
            "provides_feature_importance": self.provides_feature_importance,
        }


CATALOGUE: tuple[ModelSpec, ...] = (
    ModelSpec(
        key="logistic_regression",
        label="Logistic Regression",
        description="Linear model that estimates class probabilities. A good first baseline.",
        estimator="sklearn.linear_model:LogisticRegression",
        params=(
            ParamSpec("C", "float", 1.0, 0.01, 100, label="Inverse regularisation strength (C)"),
            ParamSpec("max_iter", "int", 200, 100, 1000, label="Maximum iterations"),
        ),
    ),
    ModelSpec(
        key="knn",
        label="k-Nearest Neighbours",
        description="Predicts the majority class among the k closest training rows.",
        estimator="sklearn.neighbors:KNeighborsClassifier",
        params=(
            ParamSpec("n_neighbors", "int", 5, 1, 50, label="Number of neighbours (k)"),
            ParamSpec("weights", "choice", "uniform", choices=("uniform", "distance"), label="Neighbour weighting"),
        ),
        provides_feature_importance=False,
    ),
    ModelSpec(
        key="decision_tree",
        label="Decision Tree",
        description="A tree of yes/no questions about the features. Easy to read.",
        estimator="sklearn.tree:DecisionTreeClassifier",
        params=(
            ParamSpec("max_depth", "int_or_none", None, 1, 50, label="Maximum depth"),
            ParamSpec("min_samples_split", "int", 2, 2, 20, label="Minimum samples to split"),
        ),
    ),
    ModelSpec(
        key="random_forest",
        label="Random Forest",
        description="Many decision trees voting together. Usually more accurate than one tree.",
        estimator="sklearn.ensemble:RandomForestClassifier",
        params=(
            ParamSpec("n_estimators", "int", 100, 10, 200, label="Number of trees"),
            ParamSpec("max_depth", "int_or_none", None, 1, 50, label="Maximum depth"),
        ),
        fixed=(("n_jobs", 1),),
    ),
)

_BY_KEY = {m.key: m for m in CATALOGUE}


def list_models() -> list[ModelSpec]:
    return list(CATALOGUE)


def get_model(key: str) -> ModelSpec:
    try:
        return _BY_KEY[key]
    except (KeyError, TypeError):
        raise UnknownModel(key) from None


def build_estimator(key: str, params: dict | None = None, seed: int = 42):
    """Create an unfitted scikit-learn estimator from catalogue defaults plus `params`.

    `random_state` is set from `seed` whenever the estimator supports it, so the
    same split and seed always give the same model (needed by TC-EVAL-01).
    """
    import importlib

    spec = get_model(key)
    module_name, class_name = spec.estimator.split(":")
    cls = getattr(importlib.import_module(module_name), class_name)
    kwargs = {**spec.defaults(), **(params or {}), **dict(spec.fixed)}
    if "random_state" in cls().get_params():
        kwargs["random_state"] = seed
    return cls(**kwargs)
