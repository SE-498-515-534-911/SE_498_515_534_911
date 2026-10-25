"""US-08: training pipeline (MLE-F-005, F-006, F-009; SAD risk R4)."""
import numpy as np
import pandas as pd
import pytest

from training import pipeline
from training.catalogue import list_models

from .conftest import make_frame


def test_split_is_stratified_and_repeatable():
    df = make_frame()
    first = pipeline.make_split(df, 'label', 'median', 0.25, 7)
    again = pipeline.make_split(df, 'label', 'median', 0.25, 7)
    other = pipeline.make_split(df, 'label', 'median', 0.25, 8)
    assert list(first.X_test.index) == list(again.X_test.index)
    assert list(first.X_test.index) != list(other.X_test.index)
    assert len(first.X_test) == 30
    assert first.y_test.value_counts().to_dict() == {'a': 10, 'b': 10, 'c': 10}
    assert 'label' not in first.X_train.columns


def test_missing_target_column_is_a_validation_error():
    with pytest.raises(pipeline.DataError) as exc:
        pipeline.make_split(make_frame(), 'nope', 'median', 0.2, 42)
    assert exc.value.code == 'VALIDATION_ERROR'
    assert "'nope'" in exc.value.message


@pytest.mark.parametrize('classes, message', [
    (('a',), 'between 2 and 20 classes'),
    (tuple(f'c{i}' for i in range(21)), 'between 2 and 20 classes'),
])
def test_target_class_rules_are_validation_errors(classes, message):
    with pytest.raises(pipeline.DataError) as exc:
        pipeline.make_split(make_frame(n_per_class=3, classes=classes), 'label', 'median', 0.2, 42)
    assert exc.value.code == 'VALIDATION_ERROR'
    assert message in exc.value.message


def test_class_with_one_row_is_a_validation_error():
    df = pd.concat([make_frame(), pd.DataFrame({'x1': [1.0], 'x2': [1.0], 'colour': ['red'], 'label': ['z']})])
    with pytest.raises(pipeline.DataError) as exc:
        pipeline.make_split(df, 'label', 'median', 0.2, 42)
    assert exc.value.code == 'VALIDATION_ERROR'
    assert 'at least 2 rows' in exc.value.message


def test_split_that_cannot_be_stratified_is_unprocessable():
    # 3 classes x 2 rows, 10% test share -> 1 test row for 3 classes.
    with pytest.raises(pipeline.DataError) as exc:
        pipeline.make_split(make_frame(n_per_class=2), 'label', 'median', 0.1, 42)
    assert exc.value.code == 'UNPROCESSABLE'


def test_drop_rows_removes_rows_with_missing_values_before_splitting():
    df = make_frame()
    split = pipeline.make_split(df, 'label', 'drop_rows', 0.2, 42)
    assert len(split.X_train) + len(split.X_test) == len(df) - 2
    assert not split.X_train.isna().any().any()


def test_drop_rows_that_leaves_nothing_is_unprocessable():
    df = make_frame()
    df['x1'] = np.nan
    with pytest.raises(pipeline.DataError) as exc:
        pipeline.make_split(df, 'label', 'drop_rows', 0.2, 42)
    assert exc.value.code == 'UNPROCESSABLE'


def test_infinite_values_are_treated_as_missing():
    df = make_frame()
    df.loc[0, 'x2'] = np.inf
    split = pipeline.make_split(df, 'label', 'drop_rows', 0.2, 42)
    assert np.isfinite(split.X_train['x2']).all()


def test_unreadable_file_is_unprocessable(tmp_path):
    bad = tmp_path / 'bad.csv'
    bad.write_bytes(b'\xff\xfe\x00\x00not text')
    with pytest.raises(pipeline.DataError) as exc:
        pipeline.read_csv(bad)
    assert exc.value.code == 'UNPROCESSABLE'
    with pytest.raises(pipeline.DataError):
        pipeline.read_csv(tmp_path / 'missing.csv')


def test_preprocessing_is_fitted_on_the_training_split_only():
    """No leakage (SAD R4): the fill value is the median of the TRAINING rows only."""
    df = make_frame()
    df.loc[df.sample(frac=0.3, random_state=1).index, 'x1'] = np.nan
    split = pipeline.make_split(df, 'label', 'median', 0.2, 42)
    pipe = pipeline.build_pipeline('logistic_regression', {}, 42, split.X_train, 'median')
    pipe.fit(split.X_train, split.y_train)
    numeric = pipe.named_steps['prepare'].named_transformers_['numeric']
    fill, scale = numeric.named_steps['fill'], numeric.named_steps['scale']
    assert fill.statistics_[0] == pytest.approx(split.X_train['x1'].median())
    assert fill.statistics_[0] != pytest.approx(df['x1'].median())
    assert scale.n_samples_seen_ == len(split.X_train)


@pytest.mark.parametrize('missing', ['mean', 'median', 'most_frequent', 'drop_rows'])
def test_every_missing_value_strategy_trains(tmp_path, missing):
    path = tmp_path / 'd.csv'
    make_frame().to_csv(path, index=False)
    fitted, split = pipeline.train(path, 'label', 'random_forest', {'n_estimators': 10}, missing, 0.2, 42)
    assert fitted.score(split.X_test, split.y_test) > 0.5


@pytest.mark.parametrize('model', [m.key for m in list_models()])
def test_every_catalogue_model_trains_and_predicts(tmp_path, model):
    path = tmp_path / 'd.csv'
    make_frame().to_csv(path, index=False)
    fitted, split = pipeline.train(path, 'label', model, {}, 'median', 0.2, 42)
    assert set(fitted.predict(split.X_test)) <= {'a', 'b', 'c'}
    assert fitted.named_steps['model'].__class__.__name__


def test_numeric_only_and_text_only_features_both_work():
    df = make_frame()
    for columns in (['x1', 'x2', 'label'], ['colour', 'label']):
        part = df[columns]
        split = pipeline.make_split(part, 'label', 'most_frequent', 0.2, 42)
        pipe = pipeline.build_pipeline('knn', {}, 42, split.X_train, 'most_frequent')
        pipe.fit(split.X_train, split.y_train)
        assert len(pipe.predict(split.X_test)) == len(split.X_test)


def test_unseen_category_in_test_rows_does_not_break_prediction():
    df = make_frame()
    split = pipeline.make_split(df, 'label', 'median', 0.2, 42)
    pipe = pipeline.build_pipeline('decision_tree', {}, 42, split.X_train)
    pipe.fit(split.X_train, split.y_train)
    unseen = split.X_test.copy()
    unseen['colour'] = 'purple'
    assert len(pipe.predict(unseen)) == len(unseen)
