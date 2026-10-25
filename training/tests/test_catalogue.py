"""US-06 / MLE-F-007: the model catalogue."""
import json

import pytest

from training import catalogue


def test_catalogue_has_exactly_the_four_models_of_table_4_3_1():
    assert [m.key for m in catalogue.list_models()] == [
        "logistic_regression",
        "knn",
        "decision_tree",
        "random_forest",
    ]


@pytest.mark.parametrize(
    "key, defaults",
    [
        ("logistic_regression", {"C": 1.0, "max_iter": 200}),
        ("knn", {"n_neighbors": 5, "weights": "uniform"}),
        ("decision_tree", {"max_depth": None, "min_samples_split": 2}),
        ("random_forest", {"n_estimators": 100, "max_depth": None}),
    ],
)
def test_defaults_match_the_srs(key, defaults):
    assert catalogue.get_model(key).defaults() == defaults


@pytest.mark.parametrize(
    "key, name, lo, hi",
    [
        ("logistic_regression", "C", 0.01, 100),
        ("logistic_regression", "max_iter", 100, 1000),
        ("knn", "n_neighbors", 1, 50),
        ("decision_tree", "max_depth", 1, 50),
        ("decision_tree", "min_samples_split", 2, 20),
        ("random_forest", "n_estimators", 10, 200),
        ("random_forest", "max_depth", 1, 50),
    ],
)
def test_permitted_ranges_match_the_srs(key, name, lo, hi):
    spec = catalogue.get_model(key).param(name)
    assert (spec.minimum, spec.maximum) == (lo, hi)


def test_every_model_has_at_least_two_editable_parameters():
    # MLE-F-008 needs at least two hyperparameters per model.
    for model in catalogue.list_models():
        assert len(model.params) >= 2


def test_unknown_model_is_rejected():
    with pytest.raises(catalogue.UnknownModel):
        catalogue.get_model("neural_net_from_the_internet")
    with pytest.raises(catalogue.UnknownModel):
        catalogue.get_model(None)


@pytest.mark.parametrize(
    "key, class_name",
    [
        ("logistic_regression", "LogisticRegression"),
        ("knn", "KNeighborsClassifier"),
        ("decision_tree", "DecisionTreeClassifier"),
        ("random_forest", "RandomForestClassifier"),
    ],
)
def test_build_estimator_returns_the_right_class(key, class_name):
    assert type(catalogue.build_estimator(key)).__name__ == class_name


def test_build_estimator_applies_parameters_and_seed():
    model = catalogue.build_estimator("random_forest", {"n_estimators": 20}, seed=7)
    assert model.n_estimators == 20
    assert model.random_state == 7
    assert catalogue.build_estimator("knn").get_params()["n_neighbors"] == 5


def test_description_is_json_serialisable_and_has_plain_language_ranges():
    for model in catalogue.list_models():
        text = json.dumps(model.describe())
        assert model.key in text
    c = catalogue.get_model("logistic_regression").param("C")
    assert c.range_text() == "a number between 0.01 and 100"
    assert catalogue.get_model("knn").param("weights").range_text() == "one of: uniform, distance"
    assert "or empty for no limit" in catalogue.get_model("decision_tree").param("max_depth").range_text()
