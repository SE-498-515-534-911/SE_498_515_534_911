import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user('tejas_01', 'tejas@example.com', 'Passw0rd1')


def test_register_page_renders(client):
    assert client.get(reverse('accounts:register')).status_code == 200


@pytest.mark.django_db
def test_register_creates_account_and_redirects_to_login(client):
    response = client.post(reverse('accounts:register'), {
        'username': 'newuser', 'email': 'new@example.com',
        'password': 'Passw0rd1', 'confirm_password': 'Passw0rd1',
        'role': 'STUDENT',
    })
    assert response.status_code == 302
    assert response.url == reverse('accounts:login')
    assert User.objects.filter(username='newuser').exists()


@pytest.mark.django_db
def test_register_with_bad_data_shows_errors(client):
    response = client.post(reverse('accounts:register'), {
        'username': 'x', 'email': 'bad', 'password': 'abc', 'confirm_password': 'abc',
    })
    assert response.status_code == 200
    assert not User.objects.exists()


def test_valid_login_and_logout(client, user):
    response = client.post(reverse('accounts:login'),
                           {'username': 'tejas_01', 'password': 'Passw0rd1'})
    assert response.status_code == 302
    assert client.get(reverse('accounts:home')).status_code == 200

    response = client.post(reverse('accounts:logout'))
    assert response.status_code == 302
    assert client.get(reverse('accounts:home')).status_code == 302


def test_wrong_password_refused(client, user):
    response = client.post(reverse('accounts:login'),
                           {'username': 'tejas_01', 'password': 'WrongPass1'})
    assert response.status_code == 200
    assert b'Incorrect username or password' in response.content
    assert '_auth_user_id' not in client.session


def test_unknown_user_refused(client, db):
    response = client.post(reverse('accounts:login'),
                           {'username': 'ghost', 'password': 'Passw0rd1'})
    assert response.status_code == 200
    assert '_auth_user_id' not in client.session


def test_home_requires_login(client, db):
    response = client.get(reverse('accounts:home'))
    assert response.status_code == 302
    assert response.url.startswith(reverse('accounts:login'))


def test_logout_rejects_get(client, user):
    client.force_login(user)
    assert client.get(reverse('accounts:logout')).status_code == 405


@pytest.mark.django_db
def test_register_form_offers_only_student_and_data_scientist(client):
    content = client.get(reverse('accounts:register')).content.decode()
    assert 'value="STUDENT"' in content
    assert 'value="DATA_SCIENTIST"' in content
    assert 'ADMIN' not in content


@pytest.mark.django_db
def test_register_as_data_scientist_sets_role(client):
    client.post(reverse('accounts:register'), {
        'username': 'ds_new', 'email': 'ds@example.com',
        'password': 'Passw0rd1', 'confirm_password': 'Passw0rd1',
        'role': 'DATA_SCIENTIST',
    })
    assert User.objects.get(username='ds_new').role == 'DATA_SCIENTIST'


@pytest.mark.django_db
def test_tampered_admin_registration_is_refused_and_creates_no_account(client):
    response = client.post(reverse('accounts:register'), {
        'username': 'sneaky', 'email': 'sneaky@example.com',
        'password': 'Passw0rd1', 'confirm_password': 'Passw0rd1',
        'role': 'ADMIN',
    })
    assert response.status_code == 200  # form shown again with an error
    assert not User.objects.filter(username='sneaky').exists()
