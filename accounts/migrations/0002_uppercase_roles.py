"""US-17 / MLE-F-002: store roles in the SAD's uppercase form.

Existing rows keep their role: 'student' -> 'STUDENT', and so on. The change
is reversible. Nothing from migration 0001 is edited.
"""

from django.db import migrations, models

LOWER_TO_UPPER = {
    'student': 'STUDENT',
    'data_scientist': 'DATA_SCIENTIST',
    'admin': 'ADMIN',
}
UPPER_TO_LOWER = {upper: lower for lower, upper in LOWER_TO_UPPER.items()}


def _convert(apps, mapping):
    # Use the historical model, as migrations must not import the real one.
    Profile = apps.get_model('accounts', 'Profile')
    for old, new in mapping.items():
        Profile.objects.filter(role=old).update(role=new)


def to_uppercase(apps, schema_editor):
    _convert(apps, LOWER_TO_UPPER)


def to_lowercase(apps, schema_editor):
    _convert(apps, UPPER_TO_LOWER)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='role',
            field=models.CharField(choices=[('STUDENT', 'Student'), ('DATA_SCIENTIST', 'Data Scientist'), ('ADMIN', 'Admin')], default='STUDENT', max_length=20),
        ),
        migrations.RunPython(to_uppercase, to_lowercase),
    ]
