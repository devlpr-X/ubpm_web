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
def test_request_new_type_choice(client):
    """Төрөл сонгоогүй үед сонголтын дэлгэц, сонгосон үед форм гарна."""
    resp = client.get(reverse("intake:request_new"))
    assert resp.status_code == 200
    assert "Ажиллагаатай утас".encode() in resp.content

    resp = client.get(reverse("intake:request_new") + "?type=working")
    assert resp.status_code == 200
    assert b"request_type" in resp.content
    # Түгжээтэй утасны анхааруулга харагдана
    assert "Түгжээтэй".encode() in resp.content

    resp = client.get(reverse("intake:request_new") + "?type=broken")
    assert resp.status_code == 200


def _formset_mgmt():
    return {
        "dev-TOTAL_FORMS": "1",
        "dev-INITIAL_FORMS": "0",
        "dev-MIN_NUM_FORMS": "1",
        "dev-MAX_NUM_FORMS": "1000",
    }


@pytest.mark.django_db
def test_submit_working_request_with_location(client):
    """Ажиллагаатай утас — нөхцөлийн талбаргүйгээр, байршилтай илгээгдэнэ."""
    cat = DeviceCategory.objects.create(name="Phone", slug="phone")
    data = {
        "request_type": "working",
        **_formset_mgmt(),
        "dev-0-category": str(cat.pk),
        "dev-0-brand": "Apple",
        "dev-0-model": "iPhone 13",
        "dev-0-quantity": "1",
        "dev-0-imei_or_serial": "",
        "customer_type": "INDIVIDUAL",
        "contact_name": "Тест Хэрэглэгч",
        "contact_phone": "99110011",
        "contact_email": "t@example.com",
        "city": "Улаанбаатар",
        "pickup_required": "on",
        "pickup_lat": "47.918800",
        "pickup_lng": "106.917600",
    }
    resp = client.post(reverse("intake:request_new") + "?type=working", data)
    assert resp.status_code == 302, getattr(resp, "context", None)
    r = IntakeRequest.objects.get()
    assert r.request_type == IntakeRequest.RequestType.WORKING
    assert r.has_location
    item = r.items.get()
    assert item.power_on_status == "UNKNOWN"  # default оноогдсон


@pytest.mark.django_db
def test_delivery_page_staff_only(client, django_user_model):
    staff = django_user_model.objects.create_user(
        email="op@ubpm.mn", password="x", role=django_user_model.Role.OPERATOR
    )
    r = IntakeRequest.objects.create(
        contact_name="A",
        contact_phone="9911",
        pickup_required=True,
        pickup_lat="47.918800",
        pickup_lng="106.917600",
    )
    client.force_login(staff)
    resp = client.get(reverse("dashboard:delivery"))
    assert resp.status_code == 200
    assert r.request_code.encode() in resp.content


@pytest.mark.django_db
def test_track_detail(client):
    r = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    resp = client.get(reverse("intake:track_detail", args=[str(r.tracking_token)]))
    assert resp.status_code == 200
    assert r.request_code.encode() in resp.content
