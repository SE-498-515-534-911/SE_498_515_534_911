
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import (
    check_password,
    identify_hasher,
    make_password,
)
from django.test import TestCase, SimpleTestCase


class PasswordHashingTests(SimpleTestCase):
    def test_password_is_not_stored_as_plaintext(self):
        raw_password = "TestPassword123!"
        password_hash = make_password(raw_password)

        self.assertNotEqual(password_hash, raw_password)
        self.assertTrue(check_password(raw_password, password_hash))

    def test_incorrect_password_is_rejected(self):
        password_hash = make_password("TestPassword123!")

        self.assertFalse(
            check_password("WrongPassword123!", password_hash)
        )

    def test_password_uses_pbkdf2(self):
        password_hash = make_password("TestPassword123!")
        hasher = identify_hasher(password_hash)

        self.assertEqual(hasher.algorithm, "pbkdf2_sha256")

    def test_passwords_use_different_salts(self):
        password = "TestPassword123!"

        first_hash = make_password(password)
        second_hash = make_password(password)

        self.assertNotEqual(first_hash, second_hash)
        self.assertTrue(check_password(password, first_hash))
        self.assertTrue(check_password(password, second_hash))


class UserPasswordStorageTests(TestCase):
    def test_user_password_is_stored_as_hash(self):
        User = get_user_model()
        raw_password = "TestPassword123!"

        user = User.objects.create_user(
            username="hash_test_user",
            password=raw_password,
        )

        user.refresh_from_db()

        self.assertNotEqual(user.password, raw_password)
        self.assertTrue(user.check_password(raw_password))
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
