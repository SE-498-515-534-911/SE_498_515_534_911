"""US-17: the role migration keeps every existing user's role."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [('accounts', '0001_initial')]
AFTER = [('accounts', '0002_uppercase_roles')]


def migrate_to(targets):
    executor = MigrationExecutor(connection)
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


@pytest.mark.django_db(transaction=True)
def test_existing_roles_are_kept_and_uppercased():
    apps = migrate_to(BEFORE)
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('accounts', 'Profile')
    # Old-style rows, as they exist in a database created before this change.
    for name, old_role in [('s', 'student'), ('d', 'data_scientist'), ('a', 'admin')]:
        user = User.objects.create(username=name)
        Profile.objects.create(user=user, role=old_role)

    apps = migrate_to(AFTER)
    Profile = apps.get_model('accounts', 'Profile')
    roles = {p.user.username: p.role for p in Profile.objects.select_related('user')}
    assert roles == {'s': 'STUDENT', 'd': 'DATA_SCIENTIST', 'a': 'ADMIN'}

    # Reversible: going back restores the old values.
    apps = migrate_to(BEFORE)
    Profile = apps.get_model('accounts', 'Profile')
    roles = {p.user.username: p.role for p in Profile.objects.select_related('user')}
    assert roles == {'s': 'student', 'd': 'data_scientist', 'a': 'admin'}

    migrate_to(AFTER)  # leave the test database fully migrated
