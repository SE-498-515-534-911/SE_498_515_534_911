from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import Role


def get_role(user):
    """Return the user's role value, or None if anonymous or without a profile."""
    if not user.is_authenticated:
        return None
    profile = getattr(user, 'profile', None)
    return profile.role if profile else None


def role_required(*roles):
    """Allow only logged-in users whose role is in ``roles``.

    Anonymous visitors are sent to the login page; authenticated users with
    the wrong role get HTTP 403.
    """
    allowed = {Role(r).value for r in roles}

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if get_role(request.user) not in allowed:
                raise PermissionDenied('Your role does not allow access to this page.')
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


class RoleRequiredMixin(AccessMixin):
    """Class-based view equivalent of ``role_required``."""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if get_role(request.user) not in {Role(r).value for r in self.allowed_roles}:
            raise PermissionDenied('Your role does not allow access to this page.')
        return super().dispatch(request, *args, **kwargs)
