"""Confusion matrix of a run's test split (US-22, MLE-F-011, SAD 4.3.5)."""
from sklearn.metrics import confusion_matrix


def build_confusion_matrix(y_true, y_pred, classes):
    """Return ``{"labels": [...], "matrix": [[...]]}``.

    Rows are the actual class and columns the predicted class, both in the
    order of ``classes`` (the model's ``classes_``). Every test row is counted
    exactly once, so all cells add up to the number of test rows. A class the
    model never predicted still gets its own (zero) column.
    """
    classes = list(classes)
    matrix = confusion_matrix(y_true, y_pred, labels=classes)
    return {
        # Labels are sent as text so numbers and words are drawn the same way.
        'labels': [str(c) for c in classes],
        # tolist() turns numpy integers into plain ints that JSON can carry.
        'matrix': matrix.tolist(),
    }
