"""US-37: the shared guard and pagination of the admin API (SAD 4.3.1, 4.3.2)."""
import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from accounts.admin_api import MAX_PAGE_SIZE, paginate, refuse_unless_admin

pytestmark = pytest.mark.django_db


def request_with(user=None, query='', method='GET'):
    from django.contrib.auth.models import AnonymousUser
    request = getattr(RequestFactory(), method.lower())('/x/' + query)
    request.user = user or AnonymousUser()
    return request


# ---- who may call ------------------------------------------------------------------------

def test_an_admin_passes_the_guard(admin_user):
    assert refuse_unless_admin(request_with(admin_user), 'GET') is None


def test_a_visitor_gets_401(db):
    response = refuse_unless_admin(request_with(), 'GET')
    assert response.status_code == 401


@pytest.mark.parametrize('fixture', ['student', 'scientist'])
def test_other_roles_get_403(request, fixture):
    response = refuse_unless_admin(request_with(request.getfixturevalue(fixture)), 'GET')
    assert response.status_code == 403


def test_a_user_without_a_profile_is_refused_by_default(db):
    user = get_user_model().objects.create_user('no_profile', 'n@example.com', 'Passw0rd1')
    user.profile.delete()
    user = get_user_model().objects.get(pk=user.pk)
    assert refuse_unless_admin(request_with(user), 'GET').status_code == 403


def test_the_wrong_method_gets_405(admin_user):
    assert refuse_unless_admin(request_with(admin_user, method='POST'), 'GET').status_code == 405


# ---- pagination --------------------------------------------------------------------------

@pytest.fixture
def many_users(db):
    User = get_user_model()
    # bulk_create skips password hashing, which is slow and not needed for paging
    User.objects.bulk_create(
        [User(username=f'u{i:02d}', email=f'u{i}@example.com') for i in range(45)]
    )
    return User.objects.filter(username__startswith='u').order_by('username')


def test_default_page_is_the_first_20(many_users, admin_user):
    items, meta, error = paginate(request_with(admin_user), many_users)
    assert error is None and len(items) == 20
    assert meta == {'page': 1, 'page_size': 20, 'total': 45, 'pages': 3}


def test_the_last_page_holds_the_rest(many_users, admin_user):
    items, meta, _ = paginate(request_with(admin_user, '?page=3'), many_users)
    assert len(items) == 5 and meta['page'] == 3


def test_a_page_past_the_end_is_empty_not_an_error(many_users, admin_user):
    items, meta, error = paginate(request_with(admin_user, '?page=99'), many_users)
    assert error is None and items == [] and meta['total'] == 45


def test_page_size_is_honoured_up_to_100(many_users, admin_user):
    items, meta, _ = paginate(request_with(admin_user, f'?page_size={MAX_PAGE_SIZE}'), many_users)
    assert len(items) == 45 and meta['pages'] == 1


@pytest.mark.parametrize('query', ['?page=0', '?page=-1', '?page=abc', '?page_size=0',
                                   '?page_size=101', '?page_size=x', '?page_size=-5'])
def test_bad_paging_parameters_give_400(many_users, admin_user, query):
    items, meta, error = paginate(request_with(admin_user, query), many_users)
    assert items is None and error.status_code == 400


def test_an_empty_list_has_one_page(db, admin_user):
    items, meta, _ = paginate(request_with(admin_user), get_user_model().objects.none())
    assert items == [] and meta['pages'] == 1
