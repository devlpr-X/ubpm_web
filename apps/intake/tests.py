import io
from datetime import timedelta

import pytest
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.intake.models import DeviceCategory, DeviceImage, DeviceItem, IntakeRequest


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
    # Нөхцөл/тоо ширхэгийн талбарууд аль ч флоуд байхгүй
    assert b"power_on_status" not in resp.content
    assert b"-quantity" not in resp.content
    assert b"-storage" not in resp.content


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
    assert item.category.slug == "phone"  # ажиллагаатай утас → үргэлж "Гар утас"


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


# ---------- Шийдэгдсэн хүсэлтийн зураг цэвэрлэх ----------


def _image_file(name="test.jpg"):
    """1x1 пиксел JPEG — жинхэнэ ImageField валидацийг давна."""
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), "white").save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def _request_with_image(status=IntakeRequest.Status.NEW):
    category, _ = DeviceCategory.objects.get_or_create(slug="phone", defaults={"name": "Гар утас"})
    intake = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", status=status
    )
    item = DeviceItem.objects.create(intake_request=intake, category=category)
    DeviceImage.objects.create(device_item=item, image=_image_file())
    return intake


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        IntakeRequest.Status.APPROVED,
        IntakeRequest.Status.PURCHASED,
        IntakeRequest.Status.CANCELLED,
    ],
)
def test_closing_a_request_schedules_image_purge(status):
    intake = _request_with_image()
    assert intake.images_purge_at is None

    intake.status = status
    intake.save(update_fields=["status", "updated_at"])

    intake.refresh_from_db()
    expected = timezone.now() + timedelta(days=settings.DEVICE_IMAGE_RETENTION_DAYS)
    assert intake.images_purge_at is not None
    assert abs((intake.images_purge_at - expected).total_seconds()) < 60


@pytest.mark.django_db
def test_reopening_a_request_cancels_the_purge():
    intake = _request_with_image(status=IntakeRequest.Status.CANCELLED)
    assert intake.images_purge_at is not None

    intake.status = IntakeRequest.Status.NEW
    intake.save(update_fields=["status", "updated_at"])

    intake.refresh_from_db()
    assert intake.images_purge_at is None


@pytest.mark.django_db
def test_purge_deletes_images_but_keeps_the_request():
    intake = _request_with_image(status=IntakeRequest.Status.PURCHASED)
    stored_name = DeviceImage.objects.get().image.name
    assert default_storage.exists(stored_name)

    # Хугацааг өнгөрсөн болгож команд ажиллуулна.
    IntakeRequest.objects.filter(pk=intake.pk).update(
        images_purge_at=timezone.now() - timedelta(minutes=1)
    )
    call_command("purge_device_images")

    intake.refresh_from_db()
    assert DeviceImage.objects.count() == 0
    assert not default_storage.exists(stored_name)
    # Хүсэлт болон төхөөрөмжийн мэдээлэл хэвээр.
    assert IntakeRequest.objects.filter(pk=intake.pk).exists()
    assert intake.items.count() == 1
    assert intake.contact_phone == "9911"
    assert intake.images_purged_at is not None


@pytest.mark.django_db
def test_purge_skips_requests_that_are_not_due_yet():
    intake = _request_with_image(status=IntakeRequest.Status.PURCHASED)

    call_command("purge_device_images")

    intake.refresh_from_db()
    assert DeviceImage.objects.count() == 1
    assert intake.images_purged_at is None


@pytest.mark.django_db
def test_purge_dry_run_changes_nothing():
    intake = _request_with_image(status=IntakeRequest.Status.CANCELLED)
    IntakeRequest.objects.filter(pk=intake.pk).update(
        images_purge_at=timezone.now() - timedelta(minutes=1)
    )

    call_command("purge_device_images", "--dry-run")

    intake.refresh_from_db()
    assert DeviceImage.objects.count() == 1
    assert intake.images_purged_at is None


@pytest.mark.django_db
def test_request_form_prefills_from_profile(client, django_user_model):
    """Нэвтэрсэн хэрэглэгчийн профайлын мэдээллээр маягт урьдчилан дүүрнэ."""
    django_user_model.objects.create_user(
        email="c@x.com",
        password="1234",
        full_name="Бат Болд",
        phone="99110011",
        district="Хан-Уул",
    )
    client.login(username="c@x.com", password="1234")

    resp = client.get(reverse("intake:request_new") + "?type=broken")
    content = resp.content.decode()
    assert 'value="Бат Болд"' in content
    assert 'value="99110011"' in content
    assert 'value="Хан-Уул"' in content
    assert 'value="c@x.com"' in content


@pytest.mark.django_db
def test_submitting_a_request_saves_contact_to_profile(client, django_user_model):
    cat = DeviceCategory.objects.create(name="Phone", slug="phone")
    user = django_user_model.objects.create_user(email="c@x.com", password="1234")
    client.login(username="c@x.com", password="1234")

    data = {
        "request_type": "broken",
        **_formset_mgmt(),
        "dev-0-category": str(cat.pk),
        "dev-0-brand": "Apple",
        "customer_type": "COMPANY",
        "company_name": "Од ХХК",
        "contact_name": "Бат Болд",
        "contact_phone": "99110011",
        "city": "Улаанбаатар",
        "district": "Хан-Уул",
        "address_line": "12-р хороо",
    }
    resp = client.post(reverse("intake:request_new") + "?type=broken", data)
    assert resp.status_code == 302

    user.refresh_from_db()
    assert user.full_name == "Бат Болд"
    assert user.phone == "99110011"
    assert user.customer_type == "COMPANY"
    assert user.company_name == "Од ХХК"
    assert user.district == "Хан-Уул"
    assert user.address_line == "12-р хороо"


@pytest.mark.django_db
def test_guest_submission_does_not_crash_profile_sync(client):
    """Зочин хүн илгээхэд профайл хадгалах алхам чимээгүй алгасагдана."""
    cat = DeviceCategory.objects.create(name="Phone", slug="phone")
    data = {
        "request_type": "broken",
        **_formset_mgmt(),
        "dev-0-category": str(cat.pk),
        "dev-0-brand": "Apple",
        "customer_type": "INDIVIDUAL",
        "contact_name": "Зочин",
        "contact_phone": "99110011",
        "contact_email": "guest@example.com",
        "city": "Улаанбаатар",
    }
    resp = client.post(reverse("intake:request_new") + "?type=broken", data)
    assert resp.status_code == 302
    assert IntakeRequest.objects.get().submitted_by is None
