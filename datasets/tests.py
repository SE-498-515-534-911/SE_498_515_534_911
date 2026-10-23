
import csv
import io
import json
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from accounts.models import Profile, Role
from .models import Dataset


class DatasetUploadTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.settings_override = override_settings(
            DATA_ROOT=self.temp_dir.name
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.user = User.objects.create_user(
            username="student1",
            password="test-password-123",
        )
        Profile.objects.update_or_create(
            user=self.user,
            defaults={"role": Role.STUDENT},
        )

    def make_csv(self):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["item_id", "category", "score"])

        for i in range(1, 22):
            score = "" if i == 1 else str(i * 10)
            writer.writerow([i, f"group-{i % 3}", score])

        return SimpleUploadedFile(
            "sample.csv",
            output.getvalue().encode("utf-8"),
            content_type="text/csv",
        )

    def test_upload_returns_preview_and_profile(self):
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/upload",
            {"file": self.make_csv()},
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        dataset_data = body["dataset"]
        profile = dataset_data["profile"]

        self.assertEqual(dataset_data["rows"], 21)
        self.assertEqual(dataset_data["columns"], 3)
        self.assertEqual(len(profile["preview"]), 20)

        self.assertEqual(
            [column["name"] for column in profile["columns"]],
            ["item_id", "category", "score"],
        )

        columns = {
            column["name"]: column
            for column in profile["columns"]
        }
        self.assertEqual(columns["item_id"]["type"], "numeric")
        self.assertEqual(columns["category"]["type"], "categorical")
        self.assertEqual(columns["score"]["type"], "numeric")
        self.assertEqual(columns["score"]["missing_values"], 1)

        self.assertTrue(
            Dataset.objects.filter(owner=self.user).exists()
        )

    def test_unauthenticated_upload_returns_401(self):
        response = self.client.post(
            "/api/upload",
            {"file": self.make_csv()},
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_role_upload_returns_403(self):
        admin = User.objects.create_user(
            username="admin1",
            password="test-password-123",
        )
        Profile.objects.update_or_create(
            user=admin,
            defaults={"role": Role.ADMIN},
        )
        self.client.force_login(admin)

        response = self.client.post(
            "/api/upload",
            {"file": self.make_csv()},
        )
        self.assertEqual(response.status_code, 403)

    def test_get_returns_405(self):
        response = self.client.get("/api/upload")
        self.assertEqual(response.status_code, 405)

    def test_missing_file_returns_400(self):
        self.client.force_login(self.user)

        response = self.client.post("/api/upload", {})
        self.assertEqual(response.status_code, 400)
