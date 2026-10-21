import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from django.views import View

from accounts.models import Role
from accounts.permissions import RoleRequiredMixin, role_required


@role_required(Role.DATA_SCIENTIST)
def sample_view(request):
    return HttpResponse('ok')


class SampleCBV(RoleRequiredMixin, View):
    allowed_roles = (Role.ADMIN,)

    def get(self, request):
        return HttpResponse('ok')


def make_request(user):
    request = RequestFactory().get('/x/')
    request.user = user
    return request


def test_decorator_allows_matching_role(scientist):
    assert sample_view(make_request(scientist)).status_code == 200


def test_decorator_denies_other_role(student):
    with pytest.raises(PermissionDenied):
        sample_view(make_request(student))


def test_mixin_allows_and_denies(admin_user, student):
    view = SampleCBV.as_view()
    assert view(make_request(admin_user)).status_code == 200
    with pytest.raises(PermissionDenied):
        view(make_request(student))


def test_decorator_rejects_unknown_role_at_definition():
    with pytest.raises(ValueError):
        role_required('superhero')
