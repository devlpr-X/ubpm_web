import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.intake.models import IntakeRequest


@pytest.fixture
def staff(db):
    u = User.objects.create_user(
        email="op@x.com", password="pw1234", role=User.Role.OPERATOR, is_staff=True
    )
    return u


@pytest.fixture
def authed(client, staff):
    client.login(email="op@x.com", password="pw1234")
    return client


@pytest.mark.django_db
def test_dashboard_pages(authed):
    r = IntakeRequest.objects.create(contact_name="X", contact_phone="9911")
    assert authed.get(reverse("dashboard:overview")).status_code == 200
    assert authed.get(reverse("dashboard:request_list")).status_code == 200
    assert authed.get(reverse("dashboard:pickup_list")).status_code == 200
    assert authed.get(reverse("dashboard:reports")).status_code == 200
    assert authed.get(reverse("dashboard:request_detail", args=[r.request_code])).status_code == 200


@pytest.mark.django_db
def test_export_csv(authed):
    IntakeRequest.objects.create(contact_name="X", contact_phone="9911")
    resp = authed.get(reverse("dashboard:export") + "?format=csv")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")


@pytest.mark.django_db
def test_export_xlsx(authed):
    IntakeRequest.objects.create(contact_name="X", contact_phone="9911")
    resp = authed.get(reverse("dashboard:export"))
    assert resp.status_code == 200
    assert "spreadsheetml" in resp["Content-Type"]


@pytest.mark.django_db
def test_change_status_creates_history(authed):
    r = IntakeRequest.objects.create(contact_name="X", contact_phone="9911")
    resp = authed.post(
        reverse("dashboard:change_status", args=[r.request_code]),
        {"new_status": IntakeRequest.Status.UNDER_REVIEW, "comment": "test"},
    )
    assert resp.status_code == 302
    r.refresh_from_db()
    assert r.status == IntakeRequest.Status.UNDER_REVIEW
    assert r.history.count() == 1


@pytest.mark.django_db
def test_anonymous_redirect_from_dashboard(client):
    resp = client.get(reverse("dashboard:overview"))
    assert resp.status_code == 302
