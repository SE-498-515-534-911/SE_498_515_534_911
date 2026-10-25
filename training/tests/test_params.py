"""US-07 / MLE-F-008: hyperparameter validation, including boundary values."""
import math

import pytest

from training.catalogue import UnknownModel
from training.params import validate_params


def errors_for(model, params):
    return {e.param: e.message for e in validate_params(model, params)[1]}


def test_empty_params_give_the_catalogue_defaults():
    clean, errors = validate_params("logistic_regression", {})
    assert errors == []
    assert clean == {"C": 1.0, "max_iter": 200}
    assert validate_params("knn", None)[0] == {"n_neighbors": 5, "weights": "uniform"}


def test_user_values_override_defaults_and_unset_ones_keep_defaults():
    clean, errors = validate_params("random_forest", {"n_estimators": 50})
    assert errors == []
    assert clean == {"n_estimators": 50, "max_depth": None}


@pytest.mark.parametrize(
    "model, name, good",
    [
        ("logistic_regression", "C", [0.01, 1, 100, 100.0]),
        ("logistic_regression", "max_iter", [100, 1000]),
        ("knn", "n_neighbors", [1, 50]),
        ("knn", "weights", ["uniform", "distance"]),
        ("decision_tree", "max_depth", [None, 1, 50]),
        ("decision_tree", "min_samples_split", [2, 20]),
        ("random_forest", "n_estimators", [10, 200]),
        ("random_forest", "max_depth", [None, 1, 50]),
    ],
)
def test_values_on_the_boundary_and_inside_are_accepted(model, name, good):
    for value in good:
        assert errors_for(model, {name: value}) == {}, (name, value)


@pytest.mark.parametrize(
    "model, name, bad",
    [
        ("logistic_regression", "C", [0, 0.009, 100.01, -5, math.inf, math.nan, "1.0", True, [1]]),
        ("logistic_regression", "max_iter", [99, 1001, 200.5, "200", True, None]),
        ("knn", "n_neighbors", [0, 51, 5.5, -1, None]),
        ("knn", "weights", ["manhattan", "", 1, None]),
        ("decision_tree", "max_depth", [0, 51, 3.5, "none", False]),
        ("decision_tree", "min_samples_split", [1, 21, None]),
        ("random_forest", "n_estimators", [9, 201, 0, 100.0, None]),
        ("random_forest", "max_depth", [0, 51, "deep"]),
    ],
)
def test_values_just_outside_or_of_the_wrong_type_are_refused(model, name, bad):
    for value in bad:
        assert name in errors_for(model, {name: value}), (name, value)


def test_error_message_names_the_parameter_and_its_range():
    # Test data of TC-MODEL-01: C = -5 must be refused with a validation message.
    message = errors_for("logistic_regression", {"C": -5})["C"]
    assert message == "C must be a number between 0.01 and 100."
    assert errors_for("knn", {"weights": "x"})["weights"] == "weights must be one of: uniform, distance."


def test_unknown_parameter_is_refused_and_lists_allowed_ones():
    message = errors_for("knn", {"algorithm": "kd_tree"})["algorithm"]
    assert "not a setting of k-Nearest Neighbours" in message
    assert "n_neighbors" in message and "weights" in message


def test_all_problems_are_reported_together():
    errors = errors_for("logistic_regression", {"C": -1, "max_iter": 5, "bogus": 1})
    assert set(errors) == {"C", "max_iter", "bogus"}


def test_params_must_be_an_object():
    clean, errors = validate_params("knn", [1, 2])
    assert clean == {} and errors[0].param == "params"


def test_unknown_model_raises():
    with pytest.raises(UnknownModel):
        validate_params("svm", {})
