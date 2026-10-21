import pytest
from django.contrib.auth import get_user_model

from accounts.models import Profile, Role
from accounts.permissions import get_role

User = get_user_model()


def test_new_account_gets_exactly_one_student_profile(db):
    user = User.objects.create_user('someone', 's@example.com', 'Passw0rd1')
    assert Profile.objects.filter(user=user).count() == 1
    assert user.profile.role == Role.STUDENT


def test_superuser_gets_admin_role(db):
    user = User.objects.create_superuser('root', 'r@example.com', 'Passw0rd1')
    assert user.profile.role == Role.ADMIN


def test_role_choices_are_the_three_expected_roles():
    assert {r.value for r in Role} == {'student', 'data_scientist', 'admin'}


def test_get_role_helper(student, admin_user):
    from django.contrib.auth.models import AnonymousUser
    assert get_role(student) == Role.STUDENT
    assert get_role(admin_user) == Role.ADMIN
    assert get_role(AnonymousUser()) is None


def test_user_without_profile_has_no_role(student):
    Profile.objects.filter(user=student).delete()
    student = User.objects.get(pk=student.pk)
    assert get_role(student) is None
