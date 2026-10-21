"""Evaluation metrics for a completed run, computed on the test split."""
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _average_for(n_classes):
    """Binary problems use the positive class; 3+ classes are macro-averaged."""
    return 'binary' if n_classes == 2 else 'macro'


def _roc_auc(y_true, y_proba, classes):
    """ROC-AUC, or None when probabilities are missing or AUC is undefined."""
    if y_proba is None:
        return None
    y_proba = np.asarray(y_proba, dtype=float)
    try:
        if len(classes) == 2:
            scores = y_proba if y_proba.ndim == 1 else y_proba[:, 1]
            return float(roc_auc_score(y_true, scores, labels=classes))
        return float(
            roc_auc_score(y_true, y_proba, labels=classes, multi_class='ovr', average='macro')
        )
    except ValueError:
        # e.g. the test split contains only one of the classes
        return None


def compute_metrics(y_true, y_pred, y_proba=None, classes=None):
    """Return accuracy, precision, recall, F1 and ROC-AUC.

    ``classes`` is the ordered label list matching the columns of ``y_proba``
    (``model.classes_``); it defaults to the sorted labels seen in ``y_true``.
    For two classes the second label is the positive class. ROC-AUC is None
    unless ``y_proba`` is given.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    if y_true.shape != y_pred.shape or y_true.size == 0:
        raise ValueError('y_true and y_pred must be non-empty and the same length.')

    classes = list(classes) if classes is not None else sorted(set(y_true.tolist()))
    average = _average_for(len(classes))
    options = {'labels': classes, 'average': average, 'zero_division': 0}
    if average == 'binary':
        options['pos_label'] = classes[1]

    return {
        'accuracy': float(accuracy_score(y_true, y_pred)),
        'precision': float(precision_score(y_true, y_pred, **options)),
        'recall': float(recall_score(y_true, y_pred, **options)),
        'f1': float(f1_score(y_true, y_pred, **options)),
        'roc_auc': _roc_auc(y_true, y_proba, classes),
    }
