"""Test data sets named in Test Plan Appendix A, generated so no binary files live in the repo."""
import io

import numpy as np
import pandas as pd


def iris_like(per_class=40, seed=0):
    """iris_like.csv: 3 balanced species, 4 numeric measurements, a few missing values."""
    rng = np.random.default_rng(seed)
    frames = []
    for i, species in enumerate(['setosa', 'versicolor', 'virginica']):
        frames.append(pd.DataFrame({
            'sepal_length': rng.normal(5 + i, 0.4, per_class).round(1),
            'sepal_width': rng.normal(3.4 - 0.3 * i, 0.3, per_class).round(1),
            'petal_length': rng.normal(1.5 + 2 * i, 0.3, per_class).round(1),
            'petal_width': rng.normal(0.2 + 0.9 * i, 0.2, per_class).round(1),
            'species': species,
        }))
    df = pd.concat(frames, ignore_index=True)
    df.loc[[4, 50, 99], 'sepal_width'] = np.nan
    return df


def sample_1000rows(seed=1):
    """sample_1000rows.csv: 1,000 rows, 5 columns (numeric and text), some missing values."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        'age': rng.integers(18, 80, 1000).astype(float),
        'income': rng.normal(50, 15, 1000).round(2),
        'city': rng.choice(['Pune', 'Delhi', 'Chennai'], 1000),
        'score': rng.normal(size=1000).round(3),
        'bought': rng.choice(['yes', 'no'], 1000),
    })
    df.loc[rng.choice(1000, 25, replace=False), 'income'] = np.nan
    df.loc[rng.choice(1000, 10, replace=False), 'city'] = None
    return df


def csv_bytes(df):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode('utf-8')


def csv_of_exactly(size):
    """A valid two-column CSV of exactly ``size`` bytes (exact_10MB.csv)."""
    head = b'a,b\n'
    row = b'1,' + b'x' * 497 + b'\n'
    rows, rest = divmod(size - len(head), len(row))
    data = head + row * (rows - 1) + b'1,' + b'x' * (497 + rest) + b'\n'
    assert len(data) == size
    return data


INVALID_FILES = {
    # name: (bytes, content type)
    'notes.txt': (b'just some notes\n', 'text/plain'),
    'empty.csv': (b'', 'text/csv'),
    'no_header.csv': (b'1,2,3\n' * 25, 'text/csv'),
    'short_19rows.csv': (b'a,b\n' + b'1,2\n' * 19, 'text/csv'),
}
