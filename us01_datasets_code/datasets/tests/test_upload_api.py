import shutil
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from datasets.models import Dataset
from datasets.services import MAX_DATASETS_PER_USER
from datasets.tests.test_validation import make_csv
from datasets.validators import MAX_BYTES

TMP = tempfile.mkdtemp()


@override_settings(DATA_ROOT=TMP)
class UploadApiTests(TestCase):
    URL = "/api/upload"

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        U = get_user_model()
        self.user = U.objects.create_user("ds_test1", password="Passw0rd1")
        self.client.force_login(self.user)

    def post(self, data=None, name="titanic.csv", mime="text/csv", **extra):
        f = SimpleUploadedFile(name, data if data is not None else make_csv(30, 4), content_type=mime)
        return self.client.post(self.URL, {"file": f, **extra})

    def test_success_201(self):
        r = self.post()
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual((body["rows"], body["columns"], body["name"]), (30, 4, "titanic.csv"))
        self.assertEqual(Dataset.objects.filter(owner=self.user).count(), 1)

    def test_file_stored_in_owner_folder_with_generated_name(self):
        r = self.post()
        ds = Dataset.objects.get(pk=r.json()["dataset_id"])
        p = Path(ds.file_path)
        self.assertTrue(p.exists())
        self.assertIn(f"{self.user.id}", p.parts)
        self.assertNotIn("titanic", p.name)

    def test_wrong_type_415_and_nothing_stored(self):
        r = self.post(name="notes.txt", mime="text/plain")
        self.assertEqual(r.status_code, 415)
        self.assertEqual(r.json()["error"]["code"], "UNSUPPORTED_MEDIA_TYPE")
        self.assertEqual(Dataset.objects.count(), 0)

    def test_too_large_413(self):
        r = self.post(data=b"a" * (MAX_BYTES + 1))
        self.assertEqual(r.status_code, 413)

    def test_empty_400(self):
        r = self.post(data=b"")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["code"], "VALIDATION_ERROR")

    def test_no_file_400(self):
        r = self.client.post(self.URL, {})
        self.assertEqual(r.status_code, 400)

    def test_login_required_401(self):
        self.client.logout()
        self.assertEqual(self.post().status_code, 401)

    def test_admin_forbidden_403(self):
        self.user.role = "ADMIN"          # stands in for the role field from the accounts app
        from datasets import views
        orig = views.upload_view
        # simulate the role attribute on the request user
        from django.test import RequestFactory
        rf = RequestFactory().post(self.URL)
        rf.user = self.user
        self.assertEqual(orig(rf).status_code, 403)

    def test_get_405(self):
        self.assertEqual(self.client.get(self.URL).status_code, 405)

    def test_21st_dataset_422(self):
        for _ in range(MAX_DATASETS_PER_USER):
            self.assertEqual(self.post().status_code, 201)
        r = self.post()
        self.assertEqual(r.status_code, 422)

    def test_quota_is_per_user(self):
        for _ in range(MAX_DATASETS_PER_USER):
            self.post()
        other = get_user_model().objects.create_user("student1", password="Passw0rd1")
        self.client.force_login(other)
        self.assertEqual(self.post().status_code, 201)

    def test_error_envelope_shape(self):
        err = self.post(data=b"").json()["error"]
        self.assertEqual(set(err), {"code", "message", "details", "request_id"})
