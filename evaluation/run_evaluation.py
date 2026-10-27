"""Evaluate a trained run (US-22, US-10; MLE-F-010, MLE-F-011; SAD 4.2.3, 4.3.5).

The training job (US-08) leaves a run in status TRAINED with a signed model
file. This module finishes the job:

1. load the model through the signed artifact store (never from a raw path);
2. rebuild the run's own train and test split from its saved settings and seed;
3. compute the metrics and the confusion matrix on the test split, and the
   metrics on the train split for comparison;
4. store the numbers as ``Metric`` rows and move the run to COMPLETED.

Any problem moves the run to FAILED with a message that is safe to show.
"""
import logging
from dataclasses import dataclass, field

from experiments.models import Metric, Run
from training import pipeline
from training.artifacts import load_artifact

from .confusion import build_confusion_matrix
from .importance import feature_importance
from .services import evaluate_model

logger = logging.getLogger(__name__)

EVALUATION_FAILED = (
    'The results could not be calculated. Please train the model again.'
)
ROC_AUC_NOTE = (
    'ROC-AUC is not shown: it could not be calculated for this model or test split.'
)


@dataclass
class RunEvaluation:
    """Everything the evaluate endpoint returns for a finished run."""

    metrics: dict          # {"test": {...}, "train": {...}}; undefined metrics are left out
    averaging: str         # "binary" for two classes, "macro" for more (MLE-F-010)
    confusion_matrix: dict  # {"labels": [...], "matrix": [[...]]} for the test split
    notes: list = field(default_factory=list)
    # Features from most to least important, or None when the model has no
    # importance (US-23); ``feature_importance_message`` then says why.
    feature_importance: list = None
    feature_importance_message: str = ''


def _present(scores):
    """Drop metrics that are not defined (None), as SAD 4.1.3 says to omit them."""
    return {name: value for name, value in scores.items() if value is not None}


def evaluate_run(run):
    """Compute the evaluation of a TRAINED or COMPLETED run (no database writes)."""
    model = load_artifact(run.owner, run.artifact)
    split = pipeline.load_split(
        run.dataset.file_path,
        run.target_column,
        run.preprocessing_json.get('missing', 'median'),
        run.split_json['test_size'],
        run.split_json['random_state'],
    )

    test_scores = evaluate_model(model, split.X_test, split.y_test)
    train_scores = evaluate_model(model, split.X_train, split.y_train)
    confusion = build_confusion_matrix(
        split.y_test, model.predict(split.X_test), model.classes_
    )

    importance = feature_importance(model, run.model_name)

    notes = [ROC_AUC_NOTE] if test_scores['roc_auc'] is None else []
    return RunEvaluation(
        metrics={'test': _present(test_scores), 'train': _present(train_scores)},
        averaging='binary' if len(model.classes_) == 2 else 'macro',
        confusion_matrix=confusion,
        notes=notes,
        feature_importance=importance.features if importance.available else None,
        feature_importance_message=importance.message,
    )


def store_metrics(run, evaluation):
    """Save the numbers as Metric rows named like ``test_accuracy`` (SAD 4.1.4).

    update_or_create makes this safe to repeat: the same run never gets two
    rows for one name, even if two requests evaluate it at the same time.
    """
    for split_name, scores in evaluation.metrics.items():
        for name, value in scores.items():
            Metric.objects.update_or_create(
                run=run, name=f'{split_name}_{name}', defaults={'value': value}
            )


def evaluate_and_complete(run):
    """Evaluate ``run``, store its metrics and mark it COMPLETED.

    Returns a RunEvaluation, or None if evaluation failed (the run is then
    FAILED). Never raises: the cause goes to the server log, not to the user.
    """
    try:
        evaluation = evaluate_run(run)
    except Exception:  # noqa: BLE001 - details are logged, the user gets a safe message
        logger.exception('Evaluation of run %s failed', run.pk)
        run.status = Run.Status.FAILED
        run.error_message = EVALUATION_FAILED
        run.save(update_fields=['status', 'error_message'])
        return None

    store_metrics(run, evaluation)
    if run.status == Run.Status.TRAINED:
        # Only the first evaluation moves the run on; later calls just re-read it.
        Run.objects.filter(pk=run.pk, status=Run.Status.TRAINED).update(
            status=Run.Status.COMPLETED
        )
        run.status = Run.Status.COMPLETED
    return evaluation
