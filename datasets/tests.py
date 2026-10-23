
import csv
import io
import json
import tempfile
import pandas as pd
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from accounts.models import Profile, Role
from .models import Dataset

from .services import split_dataset

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


class DatasetSplitTests(TestCase):
    def test_creates_stratified_train_test_split(self):
        dataframe = pd.DataFrame({
            "feature": list(range(100)),
            "target": ["A"] * 50 + ["B"] * 50,
        })

        X_train, X_test, y_train, y_test = split_dataset(
            dataframe,
            target_column="target",
        )

        self.assertEqual(len(X_test), 20)
        self.assertEqual(len(X_train), 80)
        self.assertEqual(set(y_train.unique()), {"A", "B"})
        self.assertEqual(set(y_test.unique()), {"A", "B"})
        self.assertEqual(len(X_train), len(y_train))
        self.assertEqual(len(X_test), len(y_test))


    def test_rejects_missing_target_column(self):
        dataframe = pd.DataFrame({
            "feature": [1, 2, 3, 4],
            "target": ["A", "A", "B", "B"],
        })

        with self.assertRaisesRegex(ValueError, "Target column does not exist"):
            split_dataset(dataframe, target_column="unknown")

    def test_rejects_invalid_test_size(self):
        dataframe = pd.DataFrame({
            "feature": list(range(20)),
            "target": ["A"] * 10 + ["B"] * 10,
        })

        with self.assertRaisesRegex(ValueError, "Test size"):
            split_dataset(dataframe, target_column="target", test_size=0.12)

    def test_rejects_target_with_only_one_class(self):
        dataframe = pd.DataFrame({
            "feature": list(range(4)),
            "target": ["A"] * 4,
        })

        with self.assertRaisesRegex(ValueError, "between 2 and 20 classes"):
            split_dataset(dataframe, target_column="target")

    def test_rejects_class_with_only_one_row(self):
        dataframe = pd.DataFrame({
            "feature": list(range(5)),
            "target": ["A", "A", "B", "B", "C"],
        })

        with self.assertRaisesRegex(ValueError, "at least 2 rows"):
            split_dataset(dataframe, target_column="target")


    def test_rejects_missing_target_values(self):
        dataframe = pd.DataFrame({
            "feature": [1, 2, 3, 4],
            "target": ["A", "A", "B", None],
        })

        with self.assertRaisesRegex(ValueError, "missing values"):
            split_dataset(dataframe, target_column="target")

    def test_rejects_more_than_twenty_classes(self):
        dataframe = pd.DataFrame({
            "feature": list(range(42)),
            "target": [
                label
                for label in range(21)
                for _ in range(2)
            ],
        })

        with self.assertRaisesRegex(ValueError, "between 2 and 20 classes"):
            split_dataset(dataframe, target_column="target")

    def test_rejects_impossible_stratified_split(self):
        dataframe = pd.DataFrame({
            "feature": list(range(10)),
            "target": ["A"] * 5 + ["B"] * 5,
        })

        with self.assertRaisesRegex(ValueError, "Cannot create a stratified split"):
            split_dataset(
                dataframe,
                target_column="target",
                test_size=0.10,
            )
