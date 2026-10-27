"""US-23: feature importance (MLE-F-012; SAD 4.3.5)."""
import numpy as np
import pandas as pd
import pytest

from evaluation.importance import feature_importance
from training import catalogue
from training.pipeline import build_pipeline


def make_data(n=300, classes=2, seed=0):
    """x1 decides the label completely; x2 and colour are noise."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    frame = pd.DataFrame({
        'x1': x1,
        'x2': rng.normal(size=n),
        'colour': rng.choice(['red', 'green', 'blue'], n),
    })
    if classes == 2:
        label = (x1 > 0).astype(int)
    else:                                   # three bands of x1
        label = np.digitize(x1, [-0.5, 0.5])
    return frame, pd.Series(label, name='label')


def fitted(model_key, classes=2):
    X, y = make_data(classes=classes)
    params = catalogue.get_model(model_key).defaults()
    pipe = build_pipeline(model_key, params, 42, X, 'median')
    return pipe.fit(X, y)


def names(result):
    return [row['feature'] for row in result.features]


def values(result):
    return [row['importance'] for row in result.features]


# ---- the three models that support it ----------------------------------------------

@pytest.mark.parametrize('model_key', ['logistic_regression', 'decision_tree', 'random_forest'])
def test_supported_models_list_features_in_descending_order(model_key):
    result = feature_importance(fitted(model_key), model_key)
    assert result.available and result.message == ''
    assert values(result) == sorted(values(result), reverse=True)


@pytest.mark.parametrize('model_key', ['logistic_regression', 'decision_tree', 'random_forest'])
def test_the_feature_that_decides_the_label_comes_first(model_key):
    result = feature_importance(fitted(model_key), model_key)
    assert names(result)[0] == 'x1'


@pytest.mark.parametrize('model_key', ['logistic_regression', 'decision_tree', 'random_forest'])
@pytest.mark.parametrize('classes', [2, 3])
def test_importances_are_non_negative_shares_that_add_up_to_one(model_key, classes):
    result = feature_importance(fitted(model_key, classes), model_key)
    assert all(v >= 0 for v in values(result))
    assert sum(values(result)) == pytest.approx(1.0, abs=1e-9)


def test_decision_tree_with_one_perfect_split_gives_x1_all_the_importance():
    """By construction: the label is exactly (x1 > 0), so one split on x1 is enough."""
    result = feature_importance(fitted('decision_tree'), 'decision_tree')
    assert dict(zip(names(result), values(result)))['x1'] == pytest.approx(1.0, abs=1e-9)


def test_logistic_regression_matches_the_scaled_absolute_coefficients():
    model = fitted('logistic_regression')
    result = feature_importance(model, 'logistic_regression')

    coef = np.abs(model.named_steps['model'].coef_[0])
    expected = coef / coef.sum()
    order = [n.split('__', 1)[1] for n in model.named_steps['prepare'].get_feature_names_out()]
    reference = dict(zip(order, expected))
    for row in result.features:
        assert row['importance'] == pytest.approx(reference[row['feature']], abs=1e-9)


def test_multiclass_logistic_regression_averages_over_the_classes():
    model = fitted('logistic_regression', classes=3)
    result = feature_importance(model, 'logistic_regression')

    coef = np.abs(model.named_steps['model'].coef_).mean(axis=0)
    expected = coef / coef.sum()
    order = [n.split('__', 1)[1] for n in model.named_steps['prepare'].get_feature_names_out()]
    reference = dict(zip(order, expected))
    for row in result.features:
        assert row['importance'] == pytest.approx(reference[row['feature']], abs=1e-9)


# ---- names ------------------------------------------------------------------------------

def test_names_have_no_transformer_prefix_and_one_hot_values_are_listed():
    result = feature_importance(fitted('random_forest'), 'random_forest')
    assert set(names(result)) == {'x1', 'x2', 'colour_blue', 'colour_green', 'colour_red'}
    assert not any('__' in n for n in names(result))


def test_a_column_name_containing_double_underscore_keeps_its_full_name():
    X, y = make_data()
    X = X.rename(columns={'x2': 'a__b'})
    pipe = build_pipeline('decision_tree', {}, 42, X, 'median').fit(X, y)
    assert 'a__b' in names(feature_importance(pipe, 'decision_tree'))


def test_equal_importances_are_ordered_by_name_so_the_list_is_stable():
    result = feature_importance(fitted('decision_tree'), 'decision_tree')
    zero_features = [row['feature'] for row in result.features if row['importance'] == 0]
    assert zero_features == sorted(zero_features)


# ---- models without feature importance ----------------------------------------------

def test_knn_says_clearly_that_importance_is_not_available():
    result = feature_importance(fitted('knn'), 'knn')
    assert result.available is False
    assert result.features == []
    assert result.message == 'Feature importance is not available for k-Nearest Neighbours.'


def test_every_catalogue_model_is_either_ranked_or_explained():
    for spec in catalogue.list_models():
        result = feature_importance(fitted(spec.key), spec.key)
        assert result.available == spec.provides_feature_importance
        assert bool(result.features) == result.available
        assert bool(result.message) == (not result.available)


def test_a_model_that_cannot_be_read_gives_a_safe_message_not_an_error(caplog):
    result = feature_importance(object(), 'random_forest')   # not a fitted pipeline
    assert result.available is False
    assert result.message == 'Feature importance could not be calculated for this run.'
    assert 'object' not in result.message                      # nothing internal is shown
    assert 'could not be read' in caplog.text                  # but the cause is logged
