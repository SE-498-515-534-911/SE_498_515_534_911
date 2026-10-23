
"""Preprocessing utilities for dataset preparation."""

import pandas as pd


SUPPORTED_STRATEGIES = {"drop_rows", "mean", "median", "most_frequent"}


def preprocess_dataframe(dataframe, strategy):
    """Handle missing values and one-hot encode categorical columns."""
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError("Input must be a pandas DataFrame.")

    if dataframe.empty or len(dataframe.columns) == 0:
        raise ValueError("Dataset must contain rows and columns.")

    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(
            "Unsupported strategy. Choose one of: "
            f"{', '.join(sorted(SUPPORTED_STRATEGIES))}."
        )

    result = dataframe.copy()

    if strategy == "drop_rows":
        result = result.dropna().reset_index(drop=True)
    else:
        numeric_columns = result.select_dtypes(
            include="number"
        ).columns.tolist()

        categorical_columns = result.select_dtypes(
            include=["object", "category", "string", "bool"]
        ).columns.tolist()

        if strategy in {"mean", "median"}:
            for column in numeric_columns:
                if result[column].isna().any():
                    non_missing = result[column].dropna()
                    if non_missing.empty:
                        raise ValueError(
                            f"Column '{column}' contains only missing values."
                        )

                    fill_value = (
                        non_missing.mean()
                        if strategy == "mean"
                        else non_missing.median()
                    )
                    result[column] = result[column].fillna(fill_value)

            columns_to_fill = categorical_columns
        else:
            columns_to_fill = result.columns.tolist()

        for column in columns_to_fill:
            if result[column].isna().any():
                non_missing = result[column].dropna()
                if non_missing.empty:
                    raise ValueError(
                        f"Column '{column}' contains only missing values."
                    )

                result[column] = result[column].fillna(
                    non_missing.mode().iloc[0]
                )

    if result.empty:
        raise ValueError("Preprocessing removed all rows.")

    categorical_columns = result.select_dtypes(
        include=["object", "category", "string", "bool"]
    ).columns.tolist()

    if categorical_columns:
        result = pd.get_dummies(
            result,
            columns=categorical_columns,
            dtype=int,
        )

    return result.reset_index(drop=True)
