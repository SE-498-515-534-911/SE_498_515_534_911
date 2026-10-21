from .metrics import compute_metrics


def evaluate_model(model, X_test, y_test):
    """Score a fitted model on its test split.

    Uses ``predict_proba`` for ROC-AUC when the model provides it; otherwise
    ROC-AUC is reported as None.
    """
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test) if hasattr(model, 'predict_proba') else None
    classes = getattr(model, 'classes_', None)
    return compute_metrics(y_test, y_pred, y_proba=y_proba, classes=classes)
