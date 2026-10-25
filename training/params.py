"""Hyperparameter validation (US-07, MLE-F-008).

Every value is checked BEFORE training starts. A refusal names the parameter and
its permitted range, as MLE-F-008 requires, e.g. "C must be a number between 0.01 and 100."
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .catalogue import ParamSpec, get_model


@dataclass(frozen=True)
class ParamError:
    param: str
    message: str

    def as_dict(self) -> dict:
        return {"field": f"params.{self.param}" if self.param != "params" else "params", "message": self.message}


def _is_int(value) -> bool:
    # bool is a subclass of int in Python; True/False are not valid numbers here.
    return isinstance(value, int) and not isinstance(value, bool)


def _is_real(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_one(spec: ParamSpec, value) -> str | None:
    """Return an error message, or None when `value` is acceptable for `spec`."""
    problem = f"{spec.name} must be {spec.range_text()}."
    if spec.kind == "int_or_none" and value is None:
        return None
    if spec.kind in ("int", "int_or_none"):
        if not _is_int(value) or not spec.minimum <= value <= spec.maximum:
            return problem
        return None
    if spec.kind == "float":
        if not _is_real(value) or not spec.minimum <= value <= spec.maximum:
            return problem
        return None
    if spec.kind == "choice":
        if not isinstance(value, str) or value not in spec.choices:
            return problem
        return None
    raise ValueError(f"unknown parameter kind {spec.kind!r}")  # pragma: no cover


def validate_params(model_key: str, raw) -> tuple[dict, list[ParamError]]:
    """Validate user-supplied hyperparameters for a catalogue model.

    Returns (clean_params, errors). `clean_params` always contains every
    parameter of the model: user values where given, catalogue defaults otherwise.
    When `errors` is not empty the caller must refuse the request.
    """
    spec = get_model(model_key)  # raises UnknownModel for a key outside the catalogue
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        return {}, [ParamError("params", "params must be a JSON object, for example {\"C\": 1.0}.")]

    errors: list[ParamError] = []
    known = {p.name for p in spec.params}
    for name in raw:
        if name not in known:
            allowed = ", ".join(sorted(known))
            errors.append(ParamError(str(name), f"{name} is not a setting of {spec.label}. Allowed settings: {allowed}."))

    clean = spec.defaults()
    for p in spec.params:
        if p.name in raw:
            message = _check_one(p, raw[p.name])
            if message:
                errors.append(ParamError(p.name, message))
            else:
                clean[p.name] = raw[p.name]
    return clean, errors
