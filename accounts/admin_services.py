"""Removing a dataset completely (US-37, MLE-F-016, MLE-SR-005).

Deleting a dataset must not leave anything behind that still belongs to it:
the uploaded file, the training runs made from it (and their metrics), and the
trained model files of those runs. Files are only ever deleted from inside the
application's own folders, so a damaged database row can never make this delete
some other file on the server.
"""
import logging
from pathlib import Path

from django.conf import settings
from django.db import transaction

from experiments.models import Run
from training.artifacts import user_artifact_dir

logger = logging.getLogger(__name__)


def has_active_runs(dataset):
    """True while a training job (queued or running) is still using this dataset."""
    return Run.objects.filter(dataset=dataset, status__in=Run.ACTIVE_STATUSES).exists()


def _delete_file_inside(folder, file_path):
    """Delete ``file_path`` only if it really lies inside ``folder``."""
    folder = Path(folder).resolve()
    path = Path(file_path).resolve()
    if folder not in path.parents:
        logger.warning('Not deleting %s: it is outside %s', path.name, folder)
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception('Could not delete the file of a removed dataset or model')


def remove_dataset(dataset):
    """Delete the dataset record, its runs and metrics, and every file that belongs to them.

    Database rows go first, in one transaction; files are deleted afterwards, so
    if the database step fails nothing has been lost. Call ``has_active_runs``
    first: this does not check it.
    """
    models_to_delete = [
        (run.owner, run.artifact)
        for run in Run.objects.filter(dataset=dataset, artifact__isnull=False)
        .select_related('owner', 'artifact')
    ]
    data_file = dataset.file_path

    with transaction.atomic():
        for _, artifact in models_to_delete:
            artifact.delete()          # the run keeps no model; the run itself goes with the dataset
        dataset.delete()               # cascades to the runs and their metrics

    for owner, artifact in models_to_delete:
        _delete_file_inside(user_artifact_dir(owner), user_artifact_dir(owner) / artifact.file_name)
    _delete_file_inside(settings.DATA_ROOT, data_file)
