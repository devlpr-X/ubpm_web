import pytest
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_create_user_with_email():
    u = User.objects.create_user(email="a@b.com", password="x")
    assert u.email == "a@b.com"
    assert u.role == User.Role.CUSTOMER
    assert not u.is_staff


@pytest.mark.django_db
def test_create_superuser():
    u = User.objects.create_superuser(email="root@x.com", password="x")
    assert u.is_superuser and u.is_staff
    assert u.role == User.Role.ADMIN


@pytest.mark.django_db
def test_is_staff_role():
    op = User.objects.create_user(email="op@x.com", password="x", role=User.Role.OPERATOR)
    cust = User.objects.create_user(email="c@x.com", password="x")
    assert op.is_staff_role
    assert not cust.is_staff_role


@pytest.mark.django_db
def test_login_redirects_staff_to_dashboard(client):
    User.objects.create_user(
        email="op@x.com", password="pw1234", role=User.Role.OPERATOR, is_staff=True
    )
    resp = client.post(
        reverse("accounts:login"),
        {"username": "op@x.com", "password": "pw1234"},
        follow=False,
    )
    assert resp.status_code == 302
    assert "dashboard" in resp.url
