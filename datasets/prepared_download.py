"""Download a prepared copy of a dataset (US-42, MLE-F-005; CSV safety MLE-SR-003).

``GET /api/datasets/<id>/prepared?strategy=median&keep=species`` sends the user's
own dataset back as a CSV with missing values handled and categories one-hot
encoded, using the same preprocessing as the rest of the Data Workspace
(``preprocess_dataframe``). The stored dataset is never changed.

* ``strategy``: ``mean``, ``median`` (the default), ``most_frequent`` or ``drop_rows``.
* ``keep``: optional column to leave exactly as it is, for example the target
  that will be predicted. Without it every text column is encoded.

Only the owner can download. Someone else's dataset answers 404, the same as a
dataset that does not exist (SAD DD4). The Admin cannot download (SRS Table 4.1-1).
"""
import numbers
import re
from pathlib import Path

import pandas as pd
from django.http import HttpResponse

from accounts.api_errors import error_response
from accounts.permissions import DATA_ROLES, get_role
from audit import services as audit
from audit.models import Action

from .models import Dataset
from .services import SUPPORTED_STRATEGIES, preprocess_dataframe

DEFAULT_STRATEGY = 'median'


def safe_cell(value):
    """Neutralise spreadsheet formula injection in one CSV cell (MLE-SR-003).

    Real numbers are left alone, so -5 stays a number. A text that starts with
    =, +, - or @ (after any blanks) gets a leading apostrophe, so a spreadsheet
    shows it as text instead of running it as a formula.
    """
    if value is None or value is pd.NA or (isinstance(value, float) and value != value):
        return ''                                   # missing
    if isinstance(value, numbers.Number):
        return value
    text = str(value)
    if text.lstrip(' \t\r\n\v\f').startswith(('=', '+', '-', '@')):
        return "'" + text
    return text


def neutralise_frame(prepared):
    """A copy of ``prepared`` that is safe to open in a spreadsheet.

    The column names and EVERY column that is not a number are cleaned. It must not
    depend on how pandas stores text: older versions use the ``object`` type, newer
    ones a separate string type, and a check for ``object`` alone silently skipped the
    newer one (found by the tests on a fresh install).
    """
    safe = prepared.copy()
    safe.columns = [safe_cell(name) for name in safe.columns]
    for position in range(safe.shape[1]):
        column = safe.iloc[:, position]
        if not pd.api.types.is_numeric_dtype(column):
            safe.isetitem(position, column.map(safe_cell))
    return safe


def prepare(dataframe, strategy, keep=None):
    """Return the prepared DataFrame; raises ValueError with a message safe to show."""
    if keep is None:
        return preprocess_dataframe(dataframe, strategy)

    if keep not in dataframe.columns:
        raise ValueError(f"The column '{keep}' is not in the dataset.")

    frame = dataframe
    if strategy == 'drop_rows':
        # Drop incomplete rows first, so the kept column stays lined up with the others.
        frame = frame.dropna().reset_index(drop=True)

    kept = frame[keep].reset_index(drop=True)
    others = frame.drop(columns=[keep])
    if len(others.columns) == 0:
        raise ValueError('There is nothing to prepare besides the column you chose to keep.')

    prepared = preprocess_dataframe(others, strategy)
    if keep in prepared.columns:
        raise ValueError(f"The kept column '{keep}' has the same name as an encoded column.")
    prepared[keep] = kept                           # put it back, untouched, at the end
    return prepared


def _file_name(dataset_name):
    """A safe download name such as ``iris-prepared.csv`` from the user's own file name."""
    stem = re.sub(r'[^A-Za-z0-9._-]+', '_', Path(dataset_name).stem).strip('._') or 'dataset'
    return f'{stem[:80]}-prepared.csv'


def download_prepared(request, dataset_id):
    if request.method != 'GET':
        return error_response(
            request, 'METHOD_NOT_ALLOWED', 'Only GET requests are allowed.', 405
        )
    if not request.user.is_authenticated:
        return error_response(request, 'AUTH_REQUIRED', 'Please log in to continue.', 401)
    if get_role(request.user) not in DATA_ROLES:
        return error_response(
            request, 'FORBIDDEN', 'You do not have permission to do this.', 403
        )

    dataset = Dataset.objects.filter(pk=dataset_id, owner=request.user).first()
    if dataset is None:
        if Dataset.objects.filter(pk=dataset_id).exists():
            # Someone else's dataset: refused like a missing one, but the attempt is logged.
            audit.record(
                Action.ACCESS_DENIED, user=request.user, target=f'dataset:{dataset_id}', request=request
            )
        return error_response(request, 'NOT_FOUND', 'We could not find that dataset.', 404)

    strategy = request.GET.get('strategy') or DEFAULT_STRATEGY
    if strategy not in SUPPORTED_STRATEGIES:
        return error_response(
            request, 'VALIDATION_ERROR',
            f"strategy must be one of: {', '.join(sorted(SUPPORTED_STRATEGIES))}.", 400,
            details={'field': 'strategy'},
        )
    keep = request.GET.get('keep') or None

    try:
        dataframe = pd.read_csv(dataset.file_path, encoding='utf-8-sig')
    except (OSError, UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return error_response(
            request, 'UNPROCESSABLE', 'The dataset file could not be read.', 422
        )

    try:
        prepared = prepare(dataframe, strategy, keep)
    except ValueError as exc:
        return error_response(
            request, 'VALIDATION_ERROR', str(exc), 400,
            details={'field': 'keep'} if keep and 'keep' in str(exc).lower() else None,
        )

    safe = neutralise_frame(prepared)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{_file_name(dataset.name)}"'
    safe.to_csv(response, index=False)

    # Audit log (US-38): who downloaded which dataset. Only the id is stored.
    audit.record(Action.REPORT_EXPORT, user=request.user, target=f'dataset:{dataset.pk}', request=request)
    return response
