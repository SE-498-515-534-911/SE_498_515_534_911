"""US-22 / US-10: evaluating a real trained run (MLE-F-010, MLE-F-011; TC-EVAL-01)."""
import pytest
from sklearn.metrics import accuracy_score, f1_score

from experiments.models import Metric, Run
from evaluation.run_evaluation import EVALUATION_FAILED, evaluate_and_complete
from training import pipeline
from training.artifacts import load_artifact, user_artifact_dir

from .conftest import train_run

pytestmark = pytest.mark.django_db

TOL = 0.001


def reference(run):
    """Recompute accuracy and F1 independently, straight from scikit-learn."""
    model = load_artifact(run.owner, run.artifact)
    split = pipeline.load_split(
        run.dataset.file_path, run.target_column, 'median',
        run.split_json['test_size'], run.split_json['random_state'],
    )
    predicted = model.predict(split.X_test)
    average = 'binary' if len(model.classes_) == 2 else 'macro'
    kwargs = {'pos_label': model.classes_[1]} if average == 'binary' else {}
    return {
        'accuracy': accuracy_score(split.y_test, predicted),
        'f1': f1_score(split.y_test, predicted, average=average, **kwargs),
        'test_rows': len(split.y_test),
    }


def test_a_trained_run_becomes_completed(trained_run):
    assert trained_run.status == Run.Status.TRAINED
    evaluation = evaluate_and_complete(trained_run)
    assert evaluation is not None
    trained_run.refresh_from_db()
    assert trained_run.status == Run.Status.COMPLETED


def test_test_metrics_match_the_scikit_learn_reference(trained_run):
    evaluation = evaluate_and_complete(trained_run)
    expected = reference(trained_run)
    assert evaluation.metrics['test']['accuracy'] == pytest.approx(expected['accuracy'], abs=TOL)
    assert evaluation.metrics['test']['f1'] == pytest.approx(expected['f1'], abs=TOL)


def test_confusion_matrix_cells_add_up_to_the_test_rows(trained_run):
    """Acceptance criterion of US-22."""
    evaluation = evaluate_and_complete(trained_run)
    matrix = evaluation.confusion_matrix['matrix']
    assert sum(sum(row) for row in matrix) == reference(trained_run)['test_rows']
    assert evaluation.confusion_matrix['labels'] == ['a', 'b', 'c']
    assert len(matrix) == len(matrix[0]) == 3


def test_averaging_is_macro_for_three_classes_and_binary_for_two(student):
    three = evaluate_and_complete(train_run(student))
    two = evaluate_and_complete(train_run(student, classes=('yes', 'no')))
    assert three.averaging == 'macro'
    assert two.averaging == 'binary'
    assert len(two.confusion_matrix['matrix']) == 2


def test_both_splits_are_reported_with_roc_auc(trained_run):
    evaluation = evaluate_and_complete(trained_run)
    for split in ('test', 'train'):
        assert set(evaluation.metrics[split]) == {'accuracy', 'precision', 'recall', 'f1', 'roc_auc'}
    assert evaluation.notes == []


def test_metric_rows_are_stored_with_the_split_in_the_name(trained_run):
    evaluation = evaluate_and_complete(trained_run)
    names = set(Metric.objects.filter(run=trained_run).values_list('name', flat=True))
    assert names == {f'{s}_{m}' for s in ('test', 'train')
                     for m in ('accuracy', 'precision', 'recall', 'f1', 'roc_auc')}
    stored = Metric.objects.get(run=trained_run, name='test_accuracy').value
    assert stored == pytest.approx(evaluation.metrics['test']['accuracy'])


def test_evaluating_twice_does_not_duplicate_metrics_or_change_values(trained_run):
    first = evaluate_and_complete(trained_run)
    count = Metric.objects.count()
    second = evaluate_and_complete(trained_run)   # the run is COMPLETED now
    assert Metric.objects.count() == count
    assert second.metrics == first.metrics
    assert second.confusion_matrix == first.confusion_matrix


@pytest.mark.parametrize('model_name', ['logistic_regression', 'knn', 'decision_tree', 'random_forest'])
def test_every_catalogue_model_can_be_evaluated(student, model_name):
    run = train_run(student, model_name=model_name)
    evaluation = evaluate_and_complete(run)
    assert evaluation is not None
    assert 0.0 <= evaluation.metrics['test']['accuracy'] <= 1.0


def test_a_missing_model_file_fails_the_run_with_a_safe_message(trained_run):
    (user_artifact_dir(trained_run.owner) / trained_run.artifact.file_name).unlink()
    assert evaluate_and_complete(trained_run) is None
    trained_run.refresh_from_db()
    assert trained_run.status == Run.Status.FAILED
    assert trained_run.error_message == EVALUATION_FAILED
    assert not Metric.objects.exists()


def test_a_tampered_model_file_is_never_loaded(trained_run):
    path = user_artifact_dir(trained_run.owner) / trained_run.artifact.file_name
    path.write_bytes(b'not the file the system wrote')
    assert evaluate_and_complete(trained_run) is None
    trained_run.refresh_from_db()
    assert trained_run.status == Run.Status.FAILED


def test_a_deleted_dataset_file_fails_the_run(trained_run):
    from pathlib import Path
    Path(trained_run.dataset.file_path).unlink()
    assert evaluate_and_complete(trained_run) is None
    trained_run.refresh_from_db()
    assert trained_run.status == Run.Status.FAILED


# ---- US-23: feature importance ----------------------------------------------------

@pytest.mark.parametrize('model_name', ['logistic_regression', 'decision_tree', 'random_forest'])
def test_supported_models_get_a_ranked_importance_list(student, model_name):
    evaluation = evaluate_and_complete(train_run(student, model_name=model_name))
    ranking = evaluation.feature_importance
    assert ranking is not None and evaluation.feature_importance_message == ''
    shares = [row['importance'] for row in ranking]
    assert shares == sorted(shares, reverse=True)
    assert sum(shares) == pytest.approx(1.0, abs=1e-9)
    # the dataset has x1, x2 and a text column 'colour' (one-hot encoded)
    assert {row['feature'] for row in ranking} == {
        'x1', 'x2', 'colour_blue', 'colour_green', 'colour_red'}


def test_knn_has_no_importance_but_the_run_still_completes(student):
    run = train_run(student, model_name='knn')
    evaluation = evaluate_and_complete(run)
    run.refresh_from_db()
    assert run.status == Run.Status.COMPLETED
    assert evaluation.feature_importance is None
    assert evaluation.feature_importance_message == (
        'Feature importance is not available for k-Nearest Neighbours.')
