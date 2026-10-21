import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from django.views import View

from accounts.models import Role
from accounts.permissions import RoleRequiredMixin, admin_required, data_user_required, role_required


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


# Roles for data features (upload, train, runs) per SRS Table 4.1-1 (MLE-F-002).
@data_user_required
def data_view(request):
    return HttpResponse('ok')


@admin_required
def admin_view(request):
    return HttpResponse('ok')


def test_student_and_data_scientist_may_use_data_features(student, scientist):
    assert data_view(make_request(student)).status_code == 200
    assert data_view(make_request(scientist)).status_code == 200


def test_admin_cannot_use_data_features(admin_user):
    with pytest.raises(PermissionDenied):
        data_view(make_request(admin_user))


def test_only_admin_passes_admin_required(admin_user, student, scientist):
    assert admin_view(make_request(admin_user)).status_code == 200
    for user in (student, scientist):
        with pytest.raises(PermissionDenied):
            admin_view(make_request(user))
