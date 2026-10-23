
import pandas as pd
import pytest

from datasets.services import preprocess_dataframe


@pytest.fixture
def sample_dataframe():
    return pd.DataFrame({
        "age": [20.0, None, 30.0],
        "city": ["Chennai", "Delhi", None],
    })


@pytest.mark.parametrize(
    ("strategy", "expected_rows"),
    [
        ("drop_rows", 1),
        ("mean", 3),
        ("median", 3),
        ("most_frequent", 3),
    ],
)
def test_preprocessing_strategies_remove_missing_values(
    sample_dataframe, strategy, expected_rows
):
    result = preprocess_dataframe(sample_dataframe, strategy)

    assert len(result) == expected_rows
    assert result.isna().sum().sum() == 0


def test_mean_fills_numeric_values_with_mean(sample_dataframe):
    result = preprocess_dataframe(sample_dataframe, "mean")

    assert result["age"].tolist() == [20.0, 25.0, 30.0]


def test_median_fills_numeric_values_with_median(sample_dataframe):
    result = preprocess_dataframe(sample_dataframe, "median")

    assert result["age"].tolist() == [20.0, 25.0, 30.0]


def test_categorical_features_are_one_hot_encoded(sample_dataframe):
    result = preprocess_dataframe(sample_dataframe, "mean")

    assert "city_Chennai" in result.columns
    assert "city_Delhi" in result.columns
    assert "city" not in result.columns


def test_source_dataframe_is_not_modified(sample_dataframe):
    original = sample_dataframe.copy(deep=True)

    preprocess_dataframe(sample_dataframe, "mean")

    pd.testing.assert_frame_equal(sample_dataframe, original)


def test_invalid_strategy_raises_error(sample_dataframe):
    with pytest.raises(ValueError, match="Unsupported strategy"):
        preprocess_dataframe(sample_dataframe, "unknown")


def test_non_dataframe_input_raises_error():
    with pytest.raises(ValueError, match="pandas DataFrame"):
        preprocess_dataframe([1, 2, 3], "mean")


def test_empty_dataframe_raises_error():
    with pytest.raises(ValueError, match="rows and columns"):
        preprocess_dataframe(pd.DataFrame(), "mean")


def test_all_missing_numeric_column_raises_error():
    dataframe = pd.DataFrame({
        "age": [None, None],
        "city": ["Chennai", "Delhi"],
    })

    with pytest.raises(ValueError, match="only missing values"):
        preprocess_dataframe(dataframe, "mean")


def test_drop_rows_rejects_result_with_no_rows():
    dataframe = pd.DataFrame({
        "age": [None, None],
        "city": [None, None],
    })

    with pytest.raises(ValueError, match="only missing values|removed all rows"):
        preprocess_dataframe(dataframe, "drop_rows")
