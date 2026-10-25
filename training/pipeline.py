"""Training pipeline: read, split, prepare and fit (SAD 3.5, 4.1.3; MLE-F-005, F-006, F-009).

* The split is made by the Data Workspace's ``split_dataset`` (US-05), so the
  stratification and target rules are the same everywhere.
* Missing-value filling, one-hot encoding and scaling live INSIDE a
  scikit-learn Pipeline. They are fitted on the training split only and then
  applied to the test split, which prevents data leakage (SAD risk R4).
* Problems with the user's data raise ``DataError``. Its message is written
  for the user; its ``code`` is the SAD 4.4.2 error code to answer with.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from datasets.services import split_dataset

from .catalogue import build_estimator

MISSING_STRATEGIES = ('median', 'mean', 'most_frequent', 'drop_rows')
CATEGORICAL_STRATEGIES = ('one_hot',)
MAX_ONE_HOT_CATEGORIES = 30


class DataError(Exception):
    """A problem with the user's data. The message is safe to show to the user."""

    def __init__(self, message, code='VALIDATION_ERROR'):
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class Split:
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series


def read_csv(path):
    try:
        return pd.read_csv(path, encoding='utf-8-sig')
    except (OSError, UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
        raise DataError('The dataset file could not be read as a CSV file.', 'UNPROCESSABLE') from None


def make_split(df, target_column, missing, test_size, seed):
    """Check the target rules and return a stratified, repeatable split.

    Target-rule problems are VALIDATION_ERROR (400); a split that cannot be
    stratified with these settings is UNPROCESSABLE (422), as in SAD 4.3.4.
    """
    if target_column not in df.columns:
        raise DataError(f"The target column '{target_column}' is not in the dataset.")
    df = df.replace([np.inf, -np.inf], np.nan)
    if missing == 'drop_rows':
        df = df.dropna().reset_index(drop=True)
        if df.empty:
            raise DataError('No rows are left after dropping rows with missing values.', 'UNPROCESSABLE')
    try:
        X_train, X_test, y_train, y_test = split_dataset(df, target_column, test_size, seed)
    except ValueError as exc:
        message = str(exc)
        code = 'UNPROCESSABLE' if message.startswith('Cannot create a stratified split') else 'VALIDATION_ERROR'
        raise DataError(message, code) from None
    return Split(X_train, X_test, y_train, y_test)


def load_split(file_path, target_column, missing, test_size, seed):
    """Read a dataset file and split it. Evaluation (US-10) uses this to rebuild a run's test split."""
    return make_split(read_csv(file_path), target_column, missing, test_size, seed)


def build_pipeline(model_name, params, seed, X_train, missing='median'):
    """Preprocessing + model as one scikit-learn Pipeline, so `fit` sees the training split only."""
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    numeric = list(X_train.select_dtypes(include='number').columns)
    categorical = [c for c in X_train.columns if c not in numeric]
    numeric_fill = 'most_frequent' if missing == 'drop_rows' else missing

    transformers = []
    if numeric:
        transformers.append((
            'numeric',
            Pipeline([('fill', SimpleImputer(strategy=numeric_fill)), ('scale', StandardScaler())]),
            numeric,
        ))
    if categorical:
        transformers.append((
            'categorical',
            Pipeline([
                ('fill', SimpleImputer(strategy='most_frequent')),
                ('one_hot', OneHotEncoder(
                    handle_unknown='infrequent_if_exist', max_categories=MAX_ONE_HOT_CATEGORIES,
                )),
            ]),
            categorical,
        ))
    return Pipeline([
        ('prepare', ColumnTransformer(transformers, sparse_threshold=1.0)),
        ('model', build_estimator(model_name, params, seed)),
    ])


def train(file_path, target_column, model_name, params, missing, test_size, seed):
    """Fit the selected model on the training split. Returns (fitted pipeline, split)."""
    split = load_split(file_path, target_column, missing, test_size, seed)
    pipe = build_pipeline(model_name, params, seed, split.X_train, missing)
    pipe.fit(split.X_train, split.y_train)
    return pipe, split
