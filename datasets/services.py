
"""Shared dataset upload, profiling, and preprocessing services."""

import csv
import math
import os
import uuid
from pathlib import Path

import pandas as pd
from django.conf import settings

from .errors import Unprocessable
from .models import Dataset
from .validators import validate_upload

MAX_DATASETS_PER_USER = 20
SUPPORTED_STRATEGIES = {"drop_rows", "mean", "median", "most_frequent"}


def profile_csv(file_path):
    """Return the first 20 rows and per-column type and missing-value counts."""
    with open(file_path, "r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []

        preview = []
        missing = {header: 0 for header in headers}
        all_numeric = {header: True for header in headers}
        has_value = {header: False for header in headers}

        for row in reader:
            for header in headers:
                value = (row.get(header) or "").strip()

                if not value:
                    missing[header] += 1
                    continue

                has_value[header] = True
                try:
                    number = float(value)
                    if not math.isfinite(number):
                        all_numeric[header] = False
                except ValueError:
                    all_numeric[header] = False

            if len(preview) < 20:
                preview.append([row.get(header, "") for header in headers])

    return {
        "preview": preview,
        "columns": [
            {
                "name": header,
                "type": (
                    "numeric"
                    if has_value[header] and all_numeric[header]
                    else "categorical"
                ),
                "missing_values": missing[header],
            }
            for header in headers
        ],
    }


def upload_dataset(user, uploaded, display_name=None):
    """Validate, store and profile a CSV, then create its Dataset record."""
    if Dataset.objects.filter(owner=user).count() >= MAX_DATASETS_PER_USER:
        raise Unprocessable(
            f"You already have {MAX_DATASETS_PER_USER} stored datasets. "
            "Delete one to upload another."
        )

    info = validate_upload(uploaded)

    folder = Path(settings.DATA_ROOT) / str(user.id) / "datasets"
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}.csv"

    try:
        with stored.open("wb") as output:
            for chunk in uploaded.chunks():
                output.write(chunk)

        profile = profile_csv(stored)
        name = os.path.basename(
            display_name or uploaded.name or "dataset.csv"
        )[:255]

        return Dataset.objects.create(
            owner=user,
            name=name,
            file_path=str(stored),
            size_bytes=uploaded.size,
            rows=info.rows,
            columns=info.columns,
            profile_json=profile,
        )
    except Exception:
        stored.unlink(missing_ok=True)
        raise


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
