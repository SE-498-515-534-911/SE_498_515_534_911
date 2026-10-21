from django.conf import settings
from django.contrib.auth.models import User
from django.db import models


class Role(models.TextChoices):
    """The three roles of SRS Table 4.1-1 (MLE-F-002); values match the SAD."""

    STUDENT = 'STUDENT', 'Student'
    DATA_SCIENTIST = 'DATA_SCIENTIST', 'Data Scientist'
    ADMIN = 'ADMIN', 'Admin'


# Roles a visitor may pick when registering. ADMIN is deliberately absent: an
# Admin is created only by an existing Admin or at installation (MLE-F-002).
SELF_REGISTRATION_ROLES = (Role.STUDENT, Role.DATA_SCIENTIST)


class Profile(models.Model):
    """Holds the single role of an account (US-17, MLE-F-002)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile'
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.STUDENT
    )

    def __str__(self):
        return f'{self.user} ({self.get_role_display()})'


def _user_role(user):
    """Role of this user, read from its Profile; None if there is no profile."""
    profile = getattr(user, 'profile', None)
    return profile.role if profile else None


# The SAD puts the role on the User. Swapping Django's user model now would
# break the migrations that already exist, so the role stays in Profile and is
# exposed as a read-only ``user.role`` property instead (documented deviation).
User.role = property(_user_role)


class LoginThrottle(models.Model):
    """Failed-login counter for one username (MLE-SR-007c, SAD 4.3.7).

    5 failed logins within 10 minutes block the account for 15 minutes.
    Records are per username (lower case) so unknown names behave the same as
    real ones and nothing is revealed about which accounts exist.
    """

    username = models.CharField(max_length=150, unique=True)
    failure_count = models.PositiveSmallIntegerField(default=0)
    window_started_at = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.username}: {self.failure_count} failures'
