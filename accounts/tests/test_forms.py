import pytest
from django.contrib.auth import get_user_model

from accounts.forms import RegistrationForm

User = get_user_model()

VALID = {
    'username': 'tejas_01',
    'email': 'tejas@example.com',
    'password': 'Passw0rd1',
    'confirm_password': 'Passw0rd1',
    'role': 'STUDENT',
}


def make_form(**overrides):
    return RegistrationForm({**VALID, **overrides})


@pytest.mark.django_db
def test_valid_registration_creates_hashed_user():
    form = make_form()
    assert form.is_valid(), form.errors
    user = form.save()
    assert user.check_password('Passw0rd1')
    assert user.password != 'Passw0rd1'


@pytest.mark.django_db
def test_invalid_email_rejected():
    assert 'email' in make_form(email='not-an-email').errors


@pytest.mark.django_db
def test_short_username_rejected():
    assert 'username' in make_form(username='ab').errors


@pytest.mark.django_db
def test_weak_password_rejected():
    form = make_form(password='abcdefgh', confirm_password='abcdefgh')
    assert 'password' in form.errors


@pytest.mark.django_db
def test_password_mismatch_rejected():
    assert 'confirm_password' in make_form(confirm_password='Different1').errors


@pytest.mark.django_db
def test_duplicate_username_and_email_rejected():
    make_form().save()
    form = make_form(username='TEJAS_01', email='TEJAS@example.com')
    assert 'username' in form.errors
    assert 'email' in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize('role', ['STUDENT', 'DATA_SCIENTIST'])
def test_allowed_roles_are_saved_on_the_profile(role):
    form = make_form(role=role)
    assert form.is_valid(), form.errors
    assert form.save().profile.role == role


@pytest.mark.django_db
@pytest.mark.parametrize('role', ['ADMIN', 'admin', 'SUPERUSER', 'student', ''])
def test_admin_and_unknown_roles_are_rejected(role):
    form = make_form(role=role)
    assert 'role' in form.errors


@pytest.mark.django_db
def test_missing_role_is_rejected():
    data = {k: v for k, v in VALID.items() if k != 'role'}
    assert 'role' in RegistrationForm(data).errors
