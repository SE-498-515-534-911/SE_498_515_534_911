"""Validation of the POST /api/train request body (SAD 4.3.4; MLE-F-005 to F-008)."""
import math
from dataclasses import dataclass, field

from . import catalogue
from .params import validate_params
from .pipeline import CATEGORICAL_STRATEGIES, MISSING_STRATEGIES

DEFAULT_PREPROCESSING = {'missing': 'median', 'categorical': 'one_hot'}
DEFAULT_SPLIT = {'test_size': 0.2, 'random_state': 42}
MAX_SEED = 2**31 - 1
MAX_COLUMN_NAME = 200


@dataclass
class TrainRequest:
    dataset_id: int
    target_column: str
    model: str
    params: dict
    preprocessing: dict = field(default_factory=lambda: dict(DEFAULT_PREPROCESSING))
    split: dict = field(default_factory=lambda: dict(DEFAULT_SPLIT))


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_test_size(value):
    """10% to 50% in steps of 5% (MLE-F-006)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return False
    steps = value * 20
    return abs(steps - round(steps)) < 1e-9 and 2 <= round(steps) <= 10


def _object(body, name, errors):
    value = body.get(name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        errors.append({'field': name, 'message': f'{name} must be a JSON object.'})
        return {}
    return value


def parse_train_request(body):
    """Return (TrainRequest, []) or (None, [{field, message}, ...]) listing every problem."""
    errors = []

    def fail(name, message):
        errors.append({'field': name, 'message': message})

    dataset_id = body.get('dataset_id')
    if not _is_int(dataset_id) or dataset_id < 1:
        fail('dataset_id', 'dataset_id must be a whole number of 1 or more.')

    target = body.get('target_column')
    if not isinstance(target, str) or not target.strip() or len(target) > MAX_COLUMN_NAME:
        fail('target_column', f'target_column must be the name of a column (1 to {MAX_COLUMN_NAME} characters).')

    model = body.get('model')
    params = {}
    try:
        catalogue.get_model(model)
    except catalogue.UnknownModel:
        keys = ', '.join(m.key for m in catalogue.list_models())
        fail('model', f'model must be one of: {keys}.')
    else:
        params, param_errors = validate_params(model, body.get('params'))
        errors.extend(e.as_dict() for e in param_errors)

    prep = {**DEFAULT_PREPROCESSING, **_object(body, 'preprocessing', errors)}
    if prep['missing'] not in MISSING_STRATEGIES:
        fail('preprocessing.missing', 'preprocessing.missing must be one of: ' + ', '.join(MISSING_STRATEGIES) + '.')
    if prep['categorical'] not in CATEGORICAL_STRATEGIES:
        fail('preprocessing.categorical', 'preprocessing.categorical must be one of: ' + ', '.join(CATEGORICAL_STRATEGIES) + '.')
    unknown = sorted(set(prep) - set(DEFAULT_PREPROCESSING))
    if unknown:
        fail('preprocessing', 'Unknown preprocessing setting: ' + ', '.join(map(str, unknown)) + '.')

    split = {**DEFAULT_SPLIT, **_object(body, 'split', errors)}
    if not _valid_test_size(split['test_size']):
        fail('split.test_size', 'Test size must be between 10% and 50% in steps of 5%.')
    if not _is_int(split['random_state']) or not 0 <= split['random_state'] <= MAX_SEED:
        fail('split.random_state', f'split.random_state must be a whole number between 0 and {MAX_SEED}.')
    unknown = sorted(set(split) - set(DEFAULT_SPLIT))
    if unknown:
        fail('split', 'Unknown split setting: ' + ', '.join(map(str, unknown)) + '.')

    if errors:
        return None, errors
    split['test_size'] = float(split['test_size'])
    return TrainRequest(dataset_id, target, model, params, prep, split), []
