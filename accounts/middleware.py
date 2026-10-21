from django.core.exceptions import PermissionDenied

from .models import Role
from .permissions import get_role

ADMIN_SITE_PREFIX = '/admin/'


class AdminRoleMiddleware:
    """Deny the Django admin site to logged-in users who are not Admins (403)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith(ADMIN_SITE_PREFIX)
            and request.user.is_authenticated
            and get_role(request.user) != Role.ADMIN
        ):
            raise PermissionDenied('Admin pages require the Admin role.')
        return self.get_response(request)
