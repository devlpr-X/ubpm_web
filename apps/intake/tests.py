import pytest
from django.urls import reverse

from apps.intake.models import DeviceCategory, IntakeRequest


@pytest.mark.django_db
def test_request_code_generated():
    cat = DeviceCategory.objects.create(name="Phone", slug="phone")
    r = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    assert r.request_code.startswith("REQ-")
    assert r.tracking_token is not None
    assert r.is_open
    assert cat.slug == "phone"


@pytest.mark.django_db
def test_public_pages(client):
    assert client.get(reverse("core:home")).status_code == 200
    assert client.get(reverse("core:about")).status_code == 200
    assert client.get(reverse("core:contact")).status_code == 200
    assert client.get(reverse("intake:request_new")).status_code == 200
    assert client.get(reverse("intake:track")).status_code == 200


@pytest.mark.django_db
def test_track_detail(client):
    r = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    resp = client.get(reverse("intake:track_detail", args=[str(r.tracking_token)]))
    assert resp.status_code == 200
    assert r.request_code.encode() in resp.content
