import pytest
from django.core.exceptions import ValidationError

from accounts.validators import validate_password_strength, validate_username_format


@pytest.mark.parametrize('name', ['abc', 'user_01', 'A' * 30, '___'])
def test_valid_usernames(name):
    validate_username_format(name)


@pytest.mark.parametrize('name', ['ab', 'A' * 31, 'bad name', 'bad-name', 'user@x', ''])
def test_invalid_usernames(name):
    with pytest.raises(ValidationError):
        validate_username_format(name)


@pytest.mark.parametrize('pw', ['abcdefg1', 'Passw0rd', '12345678a'])
def test_valid_passwords(pw):
    validate_password_strength(pw)


@pytest.mark.parametrize('pw', ['abc1', 'abcdefgh', '12345678', '', 'short1'])
def test_invalid_passwords(pw):
    with pytest.raises(ValidationError):
        validate_password_strength(pw)
