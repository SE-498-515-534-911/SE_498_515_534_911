"""US-22: confusion matrix values are checked against hand-counted references."""
import json

import pytest

from evaluation.confusion import build_confusion_matrix

# Same three-class example as the metric tests, counted by hand:
#   actual 0 -> predicted 0, 0, 1        row [2, 1, 0]
#   actual 1 -> predicted 1, 1, 2        row [0, 2, 1]
#   actual 2 -> predicted 2, 2, 2, 0     row [1, 0, 3]
TRUE = [0, 0, 0, 1, 1, 1, 2, 2, 2, 2]
PRED = [0, 0, 1, 1, 1, 2, 2, 2, 2, 0]


def test_matches_hand_counted_matrix():
    result = build_confusion_matrix(TRUE, PRED, [0, 1, 2])
    assert result['matrix'] == [[2, 1, 0], [0, 2, 1], [1, 0, 3]]
    assert result['labels'] == ['0', '1', '2']


def test_cells_add_up_to_the_number_of_test_rows():
    result = build_confusion_matrix(TRUE, PRED, [0, 1, 2])
    assert sum(sum(row) for row in result['matrix']) == len(TRUE)


def test_row_sums_are_the_actual_class_counts():
    result = build_confusion_matrix(TRUE, PRED, [0, 1, 2])
    assert [sum(row) for row in result['matrix']] == [3, 3, 4]


def test_binary_matrix_layout_is_actual_by_predicted():
    # TN=5, FP=1, FN=1, TP=3
    true = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]
    pred = [1, 1, 1, 0, 1, 0, 0, 0, 0, 0]
    assert build_confusion_matrix(true, pred, [0, 1])['matrix'] == [[5, 1], [1, 3]]


def test_text_labels_follow_the_class_order_given():
    result = build_confusion_matrix(['no', 'yes', 'yes'], ['no', 'no', 'yes'], ['yes', 'no'])
    assert result['labels'] == ['yes', 'no']
    assert result['matrix'] == [[1, 1], [0, 1]]


def test_a_class_never_predicted_still_has_a_zero_column():
    result = build_confusion_matrix([0, 1, 2], [0, 1, 1], [0, 1, 2])
    assert result['matrix'] == [[1, 0, 0], [0, 1, 0], [0, 1, 0]]


def test_result_is_json_serialisable():
    import numpy as np
    result = build_confusion_matrix(np.array(TRUE), np.array(PRED), np.array([0, 1, 2]))
    assert json.loads(json.dumps(result)) == result
