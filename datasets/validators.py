"""US-02: upload validation (SRS Table 4.2-1, SAD 4.3.3). Nothing is saved until every rule passes."""

import csv
import io
from dataclasses import dataclass

from .errors import ApiValidationError, PayloadTooLarge, UnsupportedMediaType

MAX_BYTES = 10 * 1024 * 1024  # exactly 10 MB is accepted
MIN_ROWS, MAX_ROWS = 20, 50_000  # data rows, header not counted
MIN_COLS, MAX_COLS = 2, 100
ALLOWED_MIME = {"text/csv", "text/plain"}


@dataclass
class CsvInfo:
    header: list
    rows: int
    columns: int


def _is_number(text):
    try:
        float(text)
        return True
    except ValueError:
        return False


def validate_upload(uploaded):
    """Return CsvInfo for a valid file, otherwise raise an ApiError (400, 413 or 415)."""
    name = (uploaded.name or "").lower()
    if not name.endswith(".csv"):
        raise UnsupportedMediaType(
            "Only CSV files are supported.", field="file"
        )

    mime = (uploaded.content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME:
        raise UnsupportedMediaType(
            "Only CSV files are supported.", field="file"
        )

    if uploaded.size > MAX_BYTES:
        raise PayloadTooLarge(
            "The file is larger than 10 MB.", field="file"
        )

    if uploaded.size == 0:
        raise ApiValidationError("The file is empty.", field="file")

    uploaded.seek(0)
    raw = uploaded.read()
    uploaded.seek(0)

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiValidationError(
            "The file must be UTF-8 encoded.", field="file"
        )

    return _check_structure(text)


def _check_structure(text):
    try:
        reader = csv.reader(io.StringIO(text))
        header = next((row for row in reader if row), None)

        if header is None:
            raise ApiValidationError(
                "The file has no header row.", field="file"
            )

        header = [column.strip() for column in header]

        if any(column == "" for column in header):
            raise ApiValidationError(
                "Header names must not be empty.", field="file"
            )

        if all(_is_number(column) for column in header):
            raise ApiValidationError(
                "The first row must be a header row with column names.",
                field="file",
            )

        if len(set(header)) != len(header):
            raise ApiValidationError(
                "Header names must be unique.", field="file"
            )

        cols = len(header)
        if cols < MIN_COLS or cols > MAX_COLS:
            raise ApiValidationError(
                f"The file must have {MIN_COLS} to {MAX_COLS} "
                f"columns (found {cols}).",
                field="file",
            )

        rows = 0
        for line_no, row in enumerate(reader, start=2):
            if not row:
                continue

            if len(row) != cols:
                raise ApiValidationError(
                    f"Row {line_no} has {len(row)} fields but "
                    f"the header has {cols}.",
                    field="file",
                )

            rows += 1
            if rows > MAX_ROWS:
                raise ApiValidationError(
                    f"The file has more than {MAX_ROWS:,} data rows.",
                    field="file",
                )

    except csv.Error:
        raise ApiValidationError(
            "The file is not a valid CSV file.", field="file"
        )

    if rows < MIN_ROWS:
        raise ApiValidationError(
            f"The file needs at least {MIN_ROWS} data rows "
            f"(found {rows}).",
            field="file",
        )

    return CsvInfo(header=header, rows=rows, columns=cols)
