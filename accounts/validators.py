import re

from django.core.exceptions import ValidationError

USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9_]{3,30}$')


def validate_username_format(value):
    """Username must be 3 to 30 characters: letters, digits or underscore."""
    if not USERNAME_PATTERN.fullmatch(value or ''):
        raise ValidationError(
            'Username must be 3 to 30 characters and contain only '
            'letters, digits and underscores.',
            code='invalid_username',
        )


def validate_password_strength(value):
    """Password needs at least 8 characters, one letter and one digit."""
    value = value or ''
    if len(value) < 8:
        raise ValidationError(
            'Password must be at least 8 characters long.',
            code='password_too_short',
        )
    if not re.search(r'[A-Za-z]', value) or not re.search(r'\d', value):
        raise ValidationError(
            'Password must contain at least one letter and one digit.',
            code='password_too_weak',
        )
