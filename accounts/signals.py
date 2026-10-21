from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, Role


@receiver(post_save, sender=get_user_model())
def create_profile(sender, instance, created, **kwargs):
    """Every new account gets exactly one profile; superusers become Admin."""
    if created:
        role = Role.ADMIN if instance.is_superuser else Role.STUDENT
        Profile.objects.create(user=instance, role=role)
