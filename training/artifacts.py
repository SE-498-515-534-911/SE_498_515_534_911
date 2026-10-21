"""Safe storage and loading of trained model files.

Model files are pickles, so loading an untrusted one can execute arbitrary
code. To prevent that:

* files are written only by ``save_artifact`` into a per-user directory under
  ``settings.MODEL_ARTIFACT_ROOT`` (outside the web root);
* each file gets a ModelArtifact record holding an HMAC-SHA256 signature made
  with the server's secret key;
* ``load_artifact`` takes a record, never a path, checks ownership and path,
  and verifies the signature *before* anything is deserialised;
* there is no function that loads an uploaded file.
"""
import hashlib
import hmac
import io
import uuid
from pathlib import Path

import joblib
from django.conf import settings

from .models import ModelArtifact


class ArtifactError(Exception):
    """Raised when an artifact cannot be safely loaded."""


def _signature(payload: bytes) -> str:
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def user_artifact_dir(user) -> Path:
    return Path(settings.MODEL_ARTIFACT_ROOT) / f'user_{user.pk}'


def save_artifact(user, model) -> ModelArtifact:
    """Serialise ``model`` into the user's private directory and record it."""
    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    payload = buffer.getvalue()

    directory = user_artifact_dir(user)
    directory.mkdir(parents=True, exist_ok=True)
    file_name = f'{uuid.uuid4().hex}.joblib'
    (directory / file_name).write_bytes(payload)

    return ModelArtifact.objects.create(
        owner=user, file_name=file_name, signature=_signature(payload)
    )


def _resolve_path(artifact: ModelArtifact) -> Path:
    directory = user_artifact_dir(artifact.owner).resolve()
    path = (directory / artifact.file_name).resolve()
    if path.parent != directory:
        raise ArtifactError('Artifact path is outside the owner directory.')
    return path


def load_artifact(user, artifact: ModelArtifact):
    """Load a model the system wrote for ``user``; refuse anything else."""
    if artifact.owner_id != user.pk:
        raise ArtifactError('This artifact belongs to another user.')

    path = _resolve_path(artifact)
    if not path.is_file():
        raise ArtifactError('Artifact file is missing.')

    payload = path.read_bytes()
    if not hmac.compare_digest(_signature(payload), artifact.signature):
        raise ArtifactError('Artifact failed integrity check; it was not written by the system.')

    return joblib.load(io.BytesIO(payload))
