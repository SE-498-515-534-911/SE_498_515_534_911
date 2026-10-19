"""US-01: store a validated upload under the owner's private folder and record it."""
import os
import uuid
from pathlib import Path

from django.conf import settings

from .errors import Unprocessable
from .models import Dataset
from .validators import validate_upload

MAX_DATASETS_PER_USER = 20


def upload_dataset(user, uploaded, display_name=None):
    if Dataset.objects.filter(owner=user).count() >= MAX_DATASETS_PER_USER:
        raise Unprocessable(f"You already have {MAX_DATASETS_PER_USER} stored datasets. Delete one to upload another.")
    info = validate_upload(uploaded)                      # raises on any problem; nothing is stored yet

    folder = Path(settings.DATA_ROOT) / str(user.id) / "datasets"
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}.csv"           # server-generated name, never the user's
    with open(stored, "wb") as out:
        for chunk in uploaded.chunks():
            out.write(chunk)

    name = os.path.basename(display_name or uploaded.name or "dataset.csv")[:255]
    try:
        return Dataset.objects.create(owner=user, name=name, file_path=str(stored),
                                      size_bytes=uploaded.size, rows=info.rows, columns=info.columns)
    except Exception:
        stored.unlink(missing_ok=True)                    # no half-saved upload is left behind
        raise
