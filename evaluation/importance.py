"""Feature importance of a trained model (US-23, MLE-F-012; SAD 4.3.5).

Which models support it is decided by the model catalogue
(``provides_feature_importance``): Logistic Regression, Decision Tree and
Random Forest do, K-Nearest Neighbours does not.

How the number is worked out:

* Decision Tree and Random Forest: the model's own ``feature_importances_``.
* Logistic Regression: the average absolute coefficient over the classes.
  The numeric features were standardised during training, so the coefficients
  are on a comparable scale.

Every model's numbers are then scaled to add up to 1, so a value reads as
"this feature's share of the total". Features are listed from most to least
important. A text column that was one-hot encoded appears once per value,
for example ``colour_red``.
"""
import logging
from dataclasses import dataclass, field

import numpy as np

from training import catalogue

logger = logging.getLogger(__name__)


@dataclass
class FeatureImportance:
    """The answer for one run: a list of features, or a clear reason there is none."""

    available: bool
    features: list = field(default_factory=list)   # [{"feature": ..., "importance": ...}]
    message: str = ''


def _unavailable(message):
    return FeatureImportance(available=False, features=[], message=message)


def _feature_names(prepare):
    """Names of the columns the model saw, without the transformer prefix.

    The preprocessing step names its outputs like ``numeric__age`` or
    ``categorical__colour_red``. Only the first ``__`` is removed, so a
    column that itself contains ``__`` keeps its full name.
    """
    names = [str(name) for name in prepare.get_feature_names_out()]
    return [name.split('__', 1)[1] if '__' in name else name for name in names]


def _raw_importances(estimator):
    """One non-negative number per feature, or None if the model has none."""
    if hasattr(estimator, 'feature_importances_'):
        return np.asarray(estimator.feature_importances_, dtype=float)
    if hasattr(estimator, 'coef_'):
        # coef_ has one row per class (a single row for two classes).
        return np.abs(np.asarray(estimator.coef_, dtype=float)).mean(axis=0)
    return None


def feature_importance(model, model_key):
    """Rank the features of a fitted pipeline for the catalogue model ``model_key``.

    Never raises: a model without importance, or one that cannot be read,
    gives ``available=False`` and a message that is safe to show the user.
    """
    spec = catalogue.get_model(model_key)
    if not spec.provides_feature_importance:
        return _unavailable(f'Feature importance is not available for {spec.label}.')

    try:
        names = _feature_names(model.named_steps['prepare'])
        raw = _raw_importances(model.named_steps['model'])
        if raw is None or len(raw) != len(names):
            raise ValueError('importances do not match the features')
    except Exception:  # noqa: BLE001 - the cause goes to the log, the user gets a safe message
        logger.exception('Feature importance could not be read for model %s', model_key)
        return _unavailable('Feature importance could not be calculated for this run.')

    total = raw.sum()
    shares = raw / total if total > 0 else raw
    # Largest first; equal values are ordered by name so the list is stable.
    ranked = sorted(zip(names, shares), key=lambda pair: (-pair[1], pair[0]))
    return FeatureImportance(
        available=True,
        features=[{'feature': name, 'importance': float(share)} for name, share in ranked],
    )
