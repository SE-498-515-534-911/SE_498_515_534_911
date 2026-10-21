"""Metric values are checked against hand-computed references (tolerance 0.001)."""
import pytest

from evaluation.metrics import compute_metrics

TOL = 0.001

# Binary: TP=3, FN=1, FP=1, TN=5
BIN_TRUE = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]
BIN_PRED = [1, 1, 1, 0, 1, 0, 0, 0, 0, 0]
BIN_PROBA = [0.9, 0.8, 0.7, 0.4, 0.6, 0.3, 0.2, 0.2, 0.1, 0.1]  # P(class 1)

# Three classes: per-class P=R=F1 of 2/3, 2/3, 3/4
MULTI_TRUE = [0, 0, 0, 1, 1, 1, 2, 2, 2, 2]
MULTI_PRED = [0, 0, 1, 1, 1, 2, 2, 2, 2, 0]


def test_binary_metrics_match_reference():
    m = compute_metrics(BIN_TRUE, BIN_PRED, y_proba=BIN_PROBA, classes=[0, 1])
    assert m['accuracy'] == pytest.approx(0.8, abs=TOL)
    assert m['precision'] == pytest.approx(0.75, abs=TOL)
    assert m['recall'] == pytest.approx(0.75, abs=TOL)
    assert m['f1'] == pytest.approx(0.75, abs=TOL)
    # 23 of 24 positive/negative pairs are ranked correctly
    assert m['roc_auc'] == pytest.approx(23 / 24, abs=TOL)


def test_binary_accepts_two_column_probabilities():
    proba = [[1 - p, p] for p in BIN_PROBA]
    m = compute_metrics(BIN_TRUE, BIN_PRED, y_proba=proba, classes=[0, 1])
    assert m['roc_auc'] == pytest.approx(23 / 24, abs=TOL)


def test_multiclass_is_macro_averaged():
    m = compute_metrics(MULTI_TRUE, MULTI_PRED)
    macro = (2 / 3 + 2 / 3 + 3 / 4) / 3
    assert m['accuracy'] == pytest.approx(0.7, abs=TOL)
    assert m['precision'] == pytest.approx(macro, abs=TOL)
    assert m['recall'] == pytest.approx(macro, abs=TOL)
    assert m['f1'] == pytest.approx(macro, abs=TOL)


def test_multiclass_roc_auc_perfect_separation_is_one():
    proba = [[1 if c == t else 0 for c in range(3)] for t in MULTI_TRUE]
    m = compute_metrics(MULTI_TRUE, MULTI_PRED, y_proba=proba, classes=[0, 1, 2])
    assert m['roc_auc'] == pytest.approx(1.0, abs=TOL)


def test_roc_auc_is_none_without_probabilities():
    assert compute_metrics(BIN_TRUE, BIN_PRED)['roc_auc'] is None
    assert compute_metrics(MULTI_TRUE, MULTI_PRED)['roc_auc'] is None


def test_roc_auc_is_none_when_test_split_has_one_class():
    m = compute_metrics([1, 1, 1], [1, 1, 0], y_proba=[0.9, 0.8, 0.4], classes=[0, 1])
    assert m['roc_auc'] is None


def test_string_labels_use_second_class_as_positive():
    y_true = ['no', 'no', 'yes', 'yes']
    y_pred = ['no', 'yes', 'yes', 'yes']
    m = compute_metrics(y_true, y_pred, classes=['no', 'yes'])
    assert m['precision'] == pytest.approx(2 / 3, abs=TOL)
    assert m['recall'] == pytest.approx(1.0, abs=TOL)


def test_no_positive_predictions_gives_zero_not_error():
    m = compute_metrics([1, 0, 1], [0, 0, 0], classes=[0, 1])
    assert m['precision'] == 0.0
    assert m['f1'] == 0.0


@pytest.mark.parametrize('true,pred', [([], []), ([1, 0], [1])])
def test_invalid_input_raises(true, pred):
    with pytest.raises(ValueError):
        compute_metrics(true, pred)
