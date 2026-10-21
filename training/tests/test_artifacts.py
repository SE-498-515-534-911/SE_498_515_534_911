import pickle

import pytest
from sklearn.linear_model import LogisticRegression

from training.artifacts import ArtifactError, load_artifact, save_artifact, user_artifact_dir
from training.models import ModelArtifact

executed = []


class Malicious:
    """Unpickling this would call ``executed.append``."""

    def __reduce__(self):
        return (executed.append, ('pwned',))


@pytest.fixture
def model():
    return LogisticRegression().fit([[0], [1], [2], [3]], [0, 0, 1, 1])


@pytest.fixture(autouse=True)
def reset_executed():
    executed.clear()


def test_save_then_load_round_trip(alice, model):
    artifact = save_artifact(alice, model)
    loaded = load_artifact(alice, artifact)
    assert loaded.predict([[0], [3]]).tolist() == model.predict([[0], [3]]).tolist()


def test_file_is_stored_in_per_user_directory(alice, bob, model):
    a = save_artifact(alice, model)
    b = save_artifact(bob, model)
    assert (user_artifact_dir(alice) / a.file_name).is_file()
    assert (user_artifact_dir(bob) / b.file_name).is_file()
    assert user_artifact_dir(alice) != user_artifact_dir(bob)


def test_default_artifact_root_is_not_a_served_location():
    from config import settings as project_settings

    root = project_settings.MODEL_ARTIFACT_ROOT.as_posix()
    assert '/static' not in root and '/media' not in root
    # Nothing in the project serves uploaded or generated files from disk.
    assert not hasattr(project_settings, 'MEDIA_ROOT')
    assert not hasattr(project_settings, 'STATIC_ROOT')


def test_other_user_cannot_load_artifact(alice, bob, model):
    artifact = save_artifact(alice, model)
    with pytest.raises(ArtifactError, match='another user'):
        load_artifact(bob, artifact)


def test_tampered_file_is_never_unpickled(alice, model):
    artifact = save_artifact(alice, model)
    path = user_artifact_dir(alice) / artifact.file_name
    path.write_bytes(pickle.dumps(Malicious()))

    with pytest.raises(ArtifactError, match='integrity'):
        load_artifact(alice, artifact)
    assert executed == []


def test_uploaded_file_dropped_in_directory_cannot_be_loaded(alice, model):
    save_artifact(alice, model)
    rogue = user_artifact_dir(alice) / 'uploaded.joblib'
    rogue.write_bytes(pickle.dumps(Malicious()))

    # No record exists for the file, so there is nothing the loader accepts.
    assert not ModelArtifact.objects.filter(file_name='uploaded.joblib').exists()
    forged = ModelArtifact(owner=alice, file_name='uploaded.joblib', signature='0' * 64)
    with pytest.raises(ArtifactError):
        load_artifact(alice, forged)
    assert executed == []


def test_path_traversal_file_name_rejected(alice, model, artifact_root):
    save_artifact(alice, model)
    outside = artifact_root / 'secret.joblib'
    outside.write_bytes(pickle.dumps(Malicious()))
    forged = ModelArtifact(owner=alice, file_name='../secret.joblib', signature='0' * 64)
    with pytest.raises(ArtifactError, match='outside'):
        load_artifact(alice, forged)
    assert executed == []


def test_missing_file_reports_error(alice, model):
    artifact = save_artifact(alice, model)
    (user_artifact_dir(alice) / artifact.file_name).unlink()
    with pytest.raises(ArtifactError, match='missing'):
        load_artifact(alice, artifact)


def test_signature_depends_on_secret_key(alice, model, settings):
    artifact = save_artifact(alice, model)
    settings.SECRET_KEY = 'a-different-secret-key'
    with pytest.raises(ArtifactError, match='integrity'):
        load_artifact(alice, artifact)
