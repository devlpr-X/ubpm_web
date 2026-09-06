"""End-to-end smoke tests for the mobile customer API."""

import io
import json
import os
import shutil
import tempfile
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.branches.models import Branch
from apps.intake.models import DeviceCategory, DeviceImage, DeviceItem, IntakeRequest
from apps.quotes.models import Pickup, Quotation

User = get_user_model()

MEDIA = tempfile.mkdtemp(prefix="ubpm-api-test-")


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(buf, format="PNG")
    return buf.getvalue()


def _png_upload(name="dev.png"):
    return SimpleUploadedFile(name, _png_bytes(), content_type="image/png")


@pytest.fixture(autouse=True)
def _clean_media():
    yield
    shutil.rmtree(MEDIA, ignore_errors=True)


@pytest.fixture
def category(db):
    return DeviceCategory.objects.create(name="Гар утас", slug="phone")


@pytest.fixture
def branch(db):
    return Branch.objects.create(name="Төв салбар", address_line="УБ хот")


@pytest.fixture
def auth_client(db):
    user = User.objects.create_user(
        email="cust@example.com", password="strongpass123", full_name="Болд"
    )
    client = APIClient()
    res = client.post(
        "/api/v1/auth/login/",
        {"email": "cust@example.com", "password": "strongpass123"},
        format="json",
    )
    assert res.status_code == 200, res.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
    return client, user


def test_health_is_public():
    res = APIClient().get("/api/v1/health/")
    assert res.status_code == 200
    assert res.data == {"status": "ok"}


@pytest.mark.django_db
def test_register_and_login():
    client = APIClient()
    res = client.post(
        "/api/v1/auth/register/",
        {"email": "New@Example.com", "password": "1234", "full_name": "Сараа"},
        format="json",
    )
    assert res.status_code == 201, res.content
    user = User.objects.get(email="new@example.com")
    assert user.role == User.Role.CUSTOMER

    res = client.post(
        "/api/v1/auth/login/",
        {"email": "new@example.com", "password": "1234"},
        format="json",
    )
    assert res.status_code == 200
    assert "access" in res.data and "refresh" in res.data


@pytest.mark.django_db
def test_register_rejects_non_pin_password():
    client = APIClient()
    res = client.post(
        "/api/v1/auth/register/",
        {"email": "bad@example.com", "password": "strongpass123"},
        format="json",
    )
    assert res.status_code == 400, res.content


@pytest.mark.django_db
def test_password_reset_with_code():
    from apps.accounts.models import PasswordResetCode

    user = User.objects.create_user(email="reset@example.com", password="1111")
    client = APIClient()

    res = client.post(
        "/api/v1/auth/password/request-code/", {"email": "reset@example.com"}, format="json"
    )
    assert res.status_code == 200, res.content

    code = PasswordResetCode.objects.filter(user=user).latest("created_at").code
    res = client.post(
        "/api/v1/auth/password/reset/",
        {"email": "reset@example.com", "code": code, "new_password": "4321"},
        format="json",
    )
    assert res.status_code == 200, res.content

    user.refresh_from_db()
    assert user.check_password("4321")

    # The code is single-use.
    res = client.post(
        "/api/v1/auth/password/reset/",
        {"email": "reset@example.com", "code": code, "new_password": "5678"},
        format="json",
    )
    assert res.status_code == 400, res.content


@pytest.mark.django_db
def test_categories_public():
    DeviceCategory.objects.create(name="Камер", slug="camera")
    res = APIClient().get("/api/v1/categories/")
    assert res.status_code == 200
    assert any(c["slug"] == "camera" for c in res.data)


def _login(email, password):
    client = APIClient()
    res = client.post(
        "/api/v1/auth/login/", {"email": email, "password": password}, format="json"
    )
    assert res.status_code == 200, res.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
    return client


@override_settings(MEDIA_ROOT=MEDIA)
@pytest.mark.django_db(transaction=True)
def test_full_request_image_and_cleanup_flow():
    # transaction=True so django-cleanup's transaction.on_commit file deletion
    # actually fires (it never runs inside a rolled-back test transaction).
    user = User.objects.create_user(
        email="cust@example.com", password="strongpass123", full_name="Болд"
    )
    category = DeviceCategory.objects.create(name="Гар утас", slug="phone")
    branch = Branch.objects.create(name="Төв салбар", address_line="УБ хот")
    client = _login("cust@example.com", "strongpass123")

    # 1. Create a request with a nested device.
    payload = {
        "contact_name": "Болд",
        "contact_phone": "99112233",
        "preferred_branch": branch.id,
        "device": {"category": category.id, "brand": "Apple", "model": "iPhone 12"},
    }
    res = client.post("/api/v1/requests/", payload, format="json")
    assert res.status_code == 201, res.content
    code = res.data["request_code"]
    req = IntakeRequest.objects.get(request_code=code)
    assert req.submitted_by == user
    assert req.source == IntakeRequest.Source.APP
    assert req.contact_email == user.email  # backfilled from account

    # 2. Upload two images -> URLs returned, files on disk.
    res = client.post(
        f"/api/v1/requests/{code}/images/",
        {"image": [_png_upload("a.png"), _png_upload("b.png")]},
        format="multipart",
    )
    assert res.status_code == 201, res.content
    assert len(res.data) == 2
    assert res.data[0]["image"].startswith("http")  # absolute URL
    img_id = res.data[0]["id"]
    paths = [img.image.path for img in DeviceImage.objects.all()]
    assert all(os.path.exists(p) for p in paths)

    # 3. Delete one image -> row gone AND file removed (django-cleanup).
    target = DeviceImage.objects.get(pk=img_id)
    target_path = target.image.path
    res = client.delete(f"/api/v1/requests/{code}/images/{img_id}/")
    assert res.status_code == 204
    assert not DeviceImage.objects.filter(pk=img_id).exists()
    assert not os.path.exists(target_path)

    # 4. Deleting the whole request removes remaining image files too.
    remaining = [img.image.path for img in DeviceImage.objects.all()]
    res = client.delete(f"/api/v1/requests/{code}/")
    assert res.status_code == 204
    assert not IntakeRequest.objects.filter(request_code=code).exists()
    assert all(not os.path.exists(p) for p in remaining)


@pytest.mark.django_db
def test_requests_are_owner_scoped(auth_client, category):
    client, user = auth_client
    other = User.objects.create_user(email="other@example.com", password="strongpass123")
    foreign = IntakeRequest.objects.create(
        contact_name="Бусад", contact_phone="88001122", submitted_by=other
    )
    # Not in my list
    res = client.get("/api/v1/requests/")
    assert res.status_code == 200
    assert all(r["contact_name"] != "Бусад" for r in res.data["results"])
    # Cannot fetch someone else's request
    res = client.get(f"/api/v1/requests/{foreign.request_code}/")
    assert res.status_code == 404


@pytest.mark.django_db
def test_accept_quote_transitions_status(auth_client):
    client, user = auth_client
    req = IntakeRequest.objects.create(
        contact_name="Болд",
        contact_phone="99112233",
        submitted_by=user,
        status=IntakeRequest.Status.PRICE_SENT,
    )
    res = client.post(f"/api/v1/requests/{req.request_code}/accept/")
    assert res.status_code == 200, res.content
    req.refresh_from_db()
    assert req.status == IntakeRequest.Status.APPROVED
    assert req.history.filter(new_status=IntakeRequest.Status.APPROVED).exists()


@pytest.mark.django_db
def test_public_tracking_by_token(auth_client):
    client, user = auth_client
    req = IntakeRequest.objects.create(
        contact_name="Болд", contact_phone="99112233", submitted_by=user
    )
    res = APIClient().get(f"/api/v1/track/{req.tracking_token}/")
    assert res.status_code == 200
    assert res.data["request_code"] == req.request_code


# ---------------------------------------------------------------------------
# Google Sign-In
# ---------------------------------------------------------------------------
GOOGLE_IDS = ["test-web-client-id"]


def _google_payload(email="g@example.com", aud="test-web-client-id", verified=True):
    return {
        "iss": "https://accounts.google.com",
        "aud": aud,
        "email": email,
        "email_verified": verified,
        "name": "Гэрэл",
    }


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=GOOGLE_IDS)
@pytest.mark.django_db
def test_google_signin_creates_user_and_returns_tokens():
    with patch("apps.accounts.google.google_id_token.verify_oauth2_token", return_value=_google_payload()):
        res = APIClient().post("/api/v1/auth/google/", {"id_token": "x"}, format="json")
    assert res.status_code == 201, res.content
    assert "access" in res.data and "refresh" in res.data
    assert res.data["user"]["email"] == "g@example.com"
    user = User.objects.get(email="g@example.com")
    assert user.role == User.Role.CUSTOMER
    assert not user.has_usable_password()


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=GOOGLE_IDS)
@pytest.mark.django_db
def test_google_signin_links_existing_user():
    User.objects.create_user(email="g@example.com", password="strongpass123")
    with patch("apps.accounts.google.google_id_token.verify_oauth2_token", return_value=_google_payload()):
        res = APIClient().post("/api/v1/auth/google/", {"id_token": "x"}, format="json")
    assert res.status_code == 200, res.content
    assert User.objects.filter(email="g@example.com").count() == 1


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=GOOGLE_IDS)
@pytest.mark.django_db
def test_google_signin_rejects_wrong_audience():
    with patch(
        "apps.accounts.google.google_id_token.verify_oauth2_token",
        return_value=_google_payload(aud="someone-elses-client-id"),
    ):
        res = APIClient().post("/api/v1/auth/google/", {"id_token": "x"}, format="json")
    assert res.status_code == 401


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=[])
@pytest.mark.django_db
def test_google_signin_requires_server_config():
    res = APIClient().post("/api/v1/auth/google/", {"id_token": "x"}, format="json")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Staff / Admin API
# ---------------------------------------------------------------------------
@pytest.fixture
def staff_client(db):
    user = User.objects.create_user(
        email="admin@ubpm.mn", password="1234", full_name="Админ", role=User.Role.ADMIN
    )
    return _login("admin@ubpm.mn", "1234"), user


@pytest.fixture
def foreign_request(db, category):
    other = User.objects.create_user(email="someone@example.com", password="9999")
    return IntakeRequest.objects.create(
        contact_name="Зочин", contact_phone="80008000", contact_email="z@example.com",
        submitted_by=other,
    )


@pytest.mark.django_db
def test_staff_dashboard_ok(staff_client, foreign_request):
    client, _ = staff_client
    res = client.get("/api/v1/staff/dashboard/")
    assert res.status_code == 200, res.content
    assert res.data["total"] == 1
    assert "by_status" in res.data and "recent" in res.data


@pytest.mark.django_db
def test_staff_dashboard_date_range_scopes_totals(staff_client, foreign_request):
    client, _ = staff_client
    # Future window → nothing in range.
    res = client.get("/api/v1/staff/dashboard/?date_from=2099-01-01&date_to=2099-12-31")
    assert res.status_code == 200
    assert res.data["total"] == 0
    assert res.data["by_status"] == []
    # Wide window → includes the request.
    res = client.get("/api/v1/staff/dashboard/?date_from=2000-01-01&date_to=2099-12-31")
    assert res.data["total"] == 1
    assert res.data["date_from"] == "2000-01-01"


@pytest.mark.django_db
def test_staff_requests_date_filter(staff_client, foreign_request):
    client, _ = staff_client
    res = client.get("/api/v1/staff/requests/?created_at__gte=2099-01-01")
    assert res.status_code == 200
    assert res.data["count"] == 0
    res = client.get("/api/v1/staff/requests/?created_at__gte=2000-01-01")
    assert res.data["count"] == 1


@pytest.mark.django_db
def test_staff_sees_all_requests(staff_client, foreign_request):
    client, _ = staff_client
    res = client.get("/api/v1/staff/requests/")
    assert res.status_code == 200, res.content
    codes = [r["request_code"] for r in res.data["results"]]
    assert foreign_request.request_code in codes  # not owner-scoped


@pytest.mark.django_db
def test_customer_cannot_access_staff_api(auth_client):
    client, _ = auth_client
    assert client.get("/api/v1/staff/dashboard/").status_code == 403
    assert client.get("/api/v1/staff/requests/").status_code == 403


@pytest.mark.django_db
def test_anonymous_cannot_access_staff_api():
    assert APIClient().get("/api/v1/staff/dashboard/").status_code == 401


@pytest.mark.django_db
def test_staff_add_quote_sets_price_sent(staff_client, foreign_request):
    client, _ = staff_client
    res = client.post(
        f"/api/v1/staff/requests/{foreign_request.request_code}/quote/",
        {"quoted_price_min": "100000", "quoted_price_max": "150000", "note": "Сайн"},
        format="json",
    )
    assert res.status_code == 200, res.content
    foreign_request.refresh_from_db()
    assert foreign_request.status == IntakeRequest.Status.PRICE_SENT
    assert foreign_request.quotes.count() == 1


@pytest.mark.django_db
def test_staff_quote_rejects_min_above_max(staff_client, foreign_request):
    client, _ = staff_client
    res = client.post(
        f"/api/v1/staff/requests/{foreign_request.request_code}/quote/",
        {"quoted_price_min": "200000", "quoted_price_max": "100000"},
        format="json",
    )
    assert res.status_code == 400, res.content


@pytest.mark.django_db
def test_staff_change_status_records_history(staff_client, foreign_request):
    client, _ = staff_client
    res = client.post(
        f"/api/v1/staff/requests/{foreign_request.request_code}/status/",
        {"new_status": IntakeRequest.Status.CANCELLED, "comment": "Хүсэлтээр"},
        format="json",
    )
    assert res.status_code == 200, res.content
    foreign_request.refresh_from_db()
    assert foreign_request.status == IntakeRequest.Status.CANCELLED
    assert foreign_request.history.filter(
        new_status=IntakeRequest.Status.CANCELLED
    ).exists()


@pytest.mark.django_db
def test_staff_assign_request(staff_client, foreign_request):
    client, staff_user = staff_client
    res = client.post(
        f"/api/v1/staff/requests/{foreign_request.request_code}/assign/",
        {"assigned_to": staff_user.id},
        format="json",
    )
    assert res.status_code == 200, res.content
    foreign_request.refresh_from_db()
    assert foreign_request.assigned_to_id == staff_user.id


@pytest.mark.django_db
def test_staff_schedule_pickup(staff_client, foreign_request):
    client, staff_user = staff_client
    res = client.post(
        f"/api/v1/staff/requests/{foreign_request.request_code}/pickup/",
        {
            "pickup_date": "2026-07-01T10:00:00Z",
            "pickup_address": "УБ, СБД",
            "assigned_staff": staff_user.id,
            "actual_buy_price": "120000",
        },
        format="json",
    )
    assert res.status_code == 200, res.content
    foreign_request.refresh_from_db()
    assert foreign_request.pickup.pickup_address == "УБ, СБД"
    # Visible in the pickup list endpoint.
    res = client.get("/api/v1/staff/pickups/")
    assert res.status_code == 200
    assert res.data["count"] == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fmt,ctype",
    [
        ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("csv", "text/csv"),
        ("pdf", "application/pdf"),
        ("png", "image/png"),
    ],
)
def test_staff_export_formats(staff_client, foreign_request, fmt, ctype):
    client, _ = staff_client
    # `fmt` (not `format`, which DRF reserves for content negotiation).
    res = client.get(f"/api/v1/staff/export/?fmt={fmt}")
    assert res.status_code == 200, res.content[:200]
    assert ctype in res["Content-Type"]
    assert int(res["Content-Length"]) > 0


@pytest.mark.django_db
def test_staff_export_rejects_customer(auth_client):
    client, _ = auth_client
    assert client.get("/api/v1/staff/export/?fmt=csv").status_code == 403


@pytest.mark.django_db
def test_create_staff_command():
    from django.core.management import call_command

    call_command("create_staff", "--email", "ops@ubpm.mn", "--pin", "4321", "--role", "ADMIN")
    user = User.objects.get(email="ops@ubpm.mn")
    assert user.role == User.Role.ADMIN
    assert user.is_staff
    assert user.check_password("4321")


# ---------------------------------------------------------------------------
# Олон төхөөрөмж — нэг хүсэлтээр (вэбийн formset-тэй ижил)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_create_request_with_multiple_devices(auth_client, category, branch):
    client, _ = auth_client
    laptop = DeviceCategory.objects.create(name="Нөүтбүүк", slug="laptop")

    res = client.post(
        "/api/v1/requests/",
        {
            "contact_name": "Болд",
            "contact_phone": "99112233",
            "preferred_branch": branch.id,
            "devices": [
                {"category": category.id, "brand": "Apple", "model": "iPhone 12"},
                {"category": laptop.id, "brand": "Lenovo", "model": "ThinkPad"},
            ],
        },
        format="json",
    )
    assert res.status_code == 201, res.content

    req = IntakeRequest.objects.get(request_code=res.data["request_code"])
    items = list(req.items.all())
    assert len(items) == 2
    assert [i.model for i in items] == ["iPhone 12", "ThinkPad"]
    # Хариу нь бүх төхөөрөмжийг буцаана — апп нэн даруй харуулна.
    assert len(res.data["items"]) == 2


@pytest.mark.django_db
def test_working_request_locks_every_device_to_phone(auth_client, category):
    """Ажиллагаатай утасны флоуд бүх мөр "Гар утас" ангилалтай болно (вэбтэй ижил)."""
    client, _ = auth_client
    laptop = DeviceCategory.objects.create(name="Нөүтбүүк", slug="laptop")

    res = client.post(
        "/api/v1/requests/",
        {
            "request_type": "WORKING",
            "contact_name": "Болд",
            "contact_phone": "99112233",
            "devices": [
                {"category": laptop.id, "model": "iPhone 11"},
                {"category": laptop.id, "model": "iPhone 13"},
            ],
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    req = IntakeRequest.objects.get(request_code=res.data["request_code"])
    assert {i.category_id for i in req.items.all()} == {category.id}


@pytest.mark.django_db
def test_create_request_requires_at_least_one_device(auth_client):
    client, _ = auth_client
    res = client.post(
        "/api/v1/requests/",
        {"contact_name": "Болд", "contact_phone": "99112233", "devices": []},
        format="json",
    )
    assert res.status_code == 400
    assert "devices" in res.data


@pytest.mark.django_db
def test_devices_over_limit_rejected(auth_client, category):
    client, _ = auth_client
    too_many = [{"category": category.id} for _ in range(21)]
    res = client.post(
        "/api/v1/requests/",
        {"contact_name": "Болд", "contact_phone": "99112233", "devices": too_many},
        format="json",
    )
    assert res.status_code == 400
    assert "devices" in res.data


@override_settings(MEDIA_ROOT=MEDIA)
@pytest.mark.django_db
def test_images_attach_to_the_named_device(auth_client, category):
    """`device` өгвөл зураг тухайн төхөөрөмж дээр очно, эс өгвөл эхнийх дээр."""
    client, _ = auth_client
    laptop = DeviceCategory.objects.create(name="Нөүтбүүк", slug="laptop")

    res = client.post(
        "/api/v1/requests/",
        {
            "contact_name": "Болд",
            "contact_phone": "99112233",
            "devices": [
                {"category": category.id, "model": "iPhone 12"},
                {"category": laptop.id, "model": "ThinkPad"},
            ],
        },
        format="json",
    )
    code = res.data["request_code"]
    req = IntakeRequest.objects.get(request_code=code)
    first, second = list(req.items.all())

    # Хоёр дахь төхөөрөмж рүү нэрлэж илгээнэ.
    res = client.post(
        f"/api/v1/requests/{code}/images/",
        {"image": _png_upload("b.png"), "device": second.id},
        format="multipart",
    )
    assert res.status_code == 201, res.content
    assert second.images.count() == 1
    assert first.images.count() == 0

    # `device` өгөхгүй бол эхнийх рүү (хуучин аппын үйлдэл хэвээр).
    res = client.post(
        f"/api/v1/requests/{code}/images/",
        {"image": _png_upload("a.png")},
        format="multipart",
    )
    assert res.status_code == 201, res.content
    assert first.images.count() == 1


@override_settings(MEDIA_ROOT=MEDIA)
@pytest.mark.django_db
def test_images_reject_device_from_another_request(auth_client, category):
    client, _ = auth_client
    codes = []
    for _ in range(2):
        res = client.post(
            "/api/v1/requests/",
            {
                "contact_name": "Болд",
                "contact_phone": "99112233",
                "devices": [{"category": category.id}],
            },
            format="json",
        )
        codes.append(res.data["request_code"])

    other_item = IntakeRequest.objects.get(request_code=codes[1]).items.first()
    res = client.post(
        f"/api/v1/requests/{codes[0]}/images/",
        {"image": _png_upload("x.png"), "device": other_item.id},
        format="multipart",
    )
    assert res.status_code == 400
    assert "device" in res.data


# ---------------------------------------------------------------------------
# Вэбтэй ижил боломжуудын шалгалт (агуулга, FAQ, зочны хүсэлт, салбар засах,
# очиж авалтын дараалал, имэйлийн оношилгоо).
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_content_blocks_are_public_and_seeded():
    """Апп нүүр/танилцуулгын текстээ вэбийн блокуудаас уншина."""
    res = APIClient().get("/api/v1/content/")
    assert res.status_code == 200, res.content
    keys = {row["key"] for row in res.data}
    assert {"home_hero", "home_how", "about_main", "contact_main"} <= keys


@pytest.mark.django_db
def test_content_block_edit_requires_staff(staff_client):
    APIClient().get("/api/v1/content/")  # блокуудыг үүсгэнэ

    anon = APIClient()
    assert anon.patch(
        "/api/v1/content/about_main/", {"title": "Хакер"}, format="json"
    ).status_code in (401, 403)

    client, _ = staff_client
    res = client.patch(
        "/api/v1/content/about_main/", {"title": "Шинэ гарчиг"}, format="json"
    )
    assert res.status_code == 200, res.content
    assert res.data["title"] == "Шинэ гарчиг"


def test_faq_is_public_and_matches_the_web():
    from apps.core.faq import FAQS

    res = APIClient().get("/api/v1/faq/")
    assert res.status_code == 200
    assert [row["question"] for row in res.data] == [row["question"] for row in FAQS]


@pytest.mark.django_db
def test_guest_can_submit_a_request_with_an_email(category):
    """Вэб шиг нэвтрэхгүйгээр хүсэлт илгээнэ — и-мэйл нь заавал."""
    payload = {
        "contact_name": "Зочин",
        "contact_phone": "99001122",
        "devices": [{"category": category.id, "brand": "Apple", "model": "iPhone 12"}],
    }
    res = APIClient().post("/api/v1/requests/", payload, format="json")
    assert res.status_code == 400
    assert "contact_email" in res.data

    payload["contact_email"] = "guest@example.com"
    res = APIClient().post("/api/v1/requests/", payload, format="json")
    assert res.status_code == 201, res.content
    intake = IntakeRequest.objects.get(request_code=res.data["request_code"])
    assert intake.submitted_by is None
    assert intake.contact_email == "guest@example.com"

    # Хяналтын кодоор нэвтрэхгүйгээр харна.
    track = APIClient().get(f"/api/v1/track/{intake.tracking_token}/")
    assert track.status_code == 200
    assert track.data["request_code"] == intake.request_code


@pytest.mark.django_db
def test_guest_request_is_linked_to_a_later_account_by_email():
    """Зочноор илгээсэн хүсэлт ижил и-мэйлтэй бүртгэлд харагдана (вэбтэй ижил)."""
    IntakeRequest.objects.create(
        contact_name="Зочин", contact_phone="99001122", contact_email="CUST@example.com"
    )
    client, _ = auth_client_for("cust@example.com")
    res = client.get("/api/v1/requests/")
    assert res.status_code == 200
    assert res.data["count"] == 1


@pytest.mark.django_db
def test_branch_edit_requires_staff(branch, staff_client):
    anon = APIClient()
    assert anon.patch(
        f"/api/v1/branches/{branch.code}/", {"name": "Хакер"}, format="json"
    ).status_code in (401, 403)

    client, _ = staff_client
    res = client.patch(
        f"/api/v1/branches/{branch.code}/",
        {"name": "Шинэ салбар", "phones": ["7774-6465", " "]},
        format="json",
    )
    assert res.status_code == 200, res.content
    assert res.data["name"] == "Шинэ салбар"
    assert res.data["phones"] == ["7774-6465"]
    assert "gallery" in res.data


@pytest.mark.django_db
def test_inactive_branch_hidden_from_public_but_visible_to_staff(branch, staff_client):
    branch.is_active = False
    branch.save(update_fields=["is_active"])

    assert APIClient().get("/api/v1/branches/").data == []
    client, _ = staff_client
    assert len(client.get("/api/v1/branches/").data) == 1


@pytest.mark.django_db
def test_pickup_queue_includes_unscheduled_requests(staff_client):
    """Товлоогүй ч очиж авахыг хүссэн хүсэлт дараалалд эхэндээ орно."""
    waiting = IntakeRequest.objects.create(
        contact_name="Хүлээгч", contact_phone="80008000", pickup_required=True
    )
    client, _ = staff_client
    res = client.get("/api/v1/staff/pickup-queue/")
    assert res.status_code == 200, res.content
    assert res.data["awaiting"] == 1
    row = res.data["results"][0]
    assert row["request_code"] == waiting.request_code
    assert row["stage"] == 0
    assert row["pickup"] is None


@pytest.mark.django_db
def test_email_status_is_staff_only(staff_client):
    assert APIClient().get("/api/v1/staff/email-status/").status_code in (401, 403)
    client, _ = staff_client
    res = client.get("/api/v1/staff/email-status/")
    assert res.status_code == 200, res.content
    assert {row["key"] for row in res.data["config"]} >= {"EMAIL_BACKEND", "SITE_URL"}
    assert res.data["probe"] is None
    assert "recent" in res.data


@pytest.mark.django_db
def test_staff_detail_carries_email_logs_and_similar_quotes(staff_client, foreign_request):
    client, _ = staff_client
    res = client.get(f"/api/v1/staff/requests/{foreign_request.request_code}/")
    assert res.status_code == 200, res.content
    assert res.data["email_logs"] == []
    assert res.data["similar_quotes"] == []


def auth_client_for(email, password="strongpass123"):
    """Шинэ хэрэглэгч үүсгээд нэвтэрсэн клиент буцаана."""
    user = User.objects.create_user(email=email, password=password)
    client = APIClient()
    res = client.post(
        "/api/v1/auth/login/", {"email": email, "password": password}, format="json"
    )
    assert res.status_code == 200, res.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
    return client, user


# ---------------------------------------------------------------------------
# AI үнийн санал — /staff/requests/<code>/price-suggestion/
# ---------------------------------------------------------------------------
GEMINI_REPLY = {
    "recommended_price": 380000,
    "suggested_min": 350000,
    "suggested_max": 420000,
    "confidence": "HIGH",
    "rationale": "Сүүлийн хэлцлүүд 350-420 мянган төгрөгийн хооронд байна.",
    "comparables": ["REQ-1"],
}


def _gemini_ok(payload=None):
    """Interactions API-ийн амжилттай хариуг дуурайсан хуурамч response."""
    body = json.dumps(payload if payload is not None else GEMINI_REPLY, ensure_ascii=False)
    fake = Mock(status_code=200, text=body)
    fake.json.return_value = {
        "id": "v1_test",
        "status": "completed",
        "steps": [{"type": "model_output", "content": [{"type": "text", "text": body}]}],
    }
    return fake


def _prompt_context(post):
    """Загварт илгээсэн prompt дотор шигтгэсэн JSON контекстийг задална."""
    prompt = post.call_args.kwargs["json"]["input"]
    return json.loads(prompt[prompt.index("{") : prompt.rindex("}") + 1])


def _phone(intake, category, brand="Apple", model="iPhone 13"):
    return DeviceItem.objects.create(
        intake_request=intake, category=category, brand=brand, model=model
    )


def _quoted(category, brand="Apple", model="iPhone 13", low=300000, high=420000, final=None):
    """Үнэ өгөгдсөн өмнөх хүсэлт — жишиг мөр болно."""
    intake = IntakeRequest.objects.create(contact_name="Өмнөх", contact_phone="9911")
    _phone(intake, category, brand=brand, model=model)
    Quotation.objects.create(
        intake_request=intake,
        quoted_price_min=low,
        quoted_price_max=high,
        final_offer_price=final,
    )
    return intake


@pytest.fixture
def priced_request(db, category):
    """Үнэ тогтоох гэж буй хүсэлт + 22 ижил төстэй хуучин хэлцэл."""
    current = IntakeRequest.objects.create(
        contact_name="Болд", contact_phone="9900", expected_price=400000
    )
    _phone(current, category)
    for _ in range(22):
        _quoted(category)
    return current


@pytest.mark.django_db
@override_settings(GEMINI_API_KEY="test-key", GEMINI_MODEL="gemini-3.8-flash")
def test_price_suggestion_sends_the_last_twenty_deals_and_returns_a_price(
    staff_client, priced_request
):
    client, _ = staff_client
    with patch("apps.quotes.ai_pricing.requests.post", return_value=_gemini_ok()) as post:
        res = client.post(
            f"/api/v1/staff/requests/{priced_request.request_code}/price-suggestion/"
        )

    assert res.status_code == 200, res.content
    assert res.data["comparables_count"] == 20
    assert res.data["suggestion"]["recommended_price"] == 380000

    # Загварт очсон prompt дотор 20 жишиг хэлцэл ба одоогийн захиалга хоёулаа байна.
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "gemini-3.8-flash"
    context = _prompt_context(post)
    assert len(context["similar_deals"]) == 20
    assert context["current_request"]["request_code"] == priced_request.request_code
    assert context["current_request"]["expected_price"] == 400000
    assert post.call_args.kwargs["headers"]["x-goog-api-key"] == "test-key"


@pytest.mark.django_db
@override_settings(GEMINI_API_KEY="test-key")
def test_price_suggestion_weighs_the_actual_buy_price(staff_client, category):
    """Бодит худалдан авсан үнэ бол хамгийн хүчтэй дохио — заавал загварт очно."""
    current = IntakeRequest.objects.create(contact_name="Болд", contact_phone="9900")
    _phone(current, category)
    done = _quoted(category, final=390000)
    Pickup.objects.create(
        intake_request=done,
        pickup_date=timezone.now(),
        pickup_address="УБ",
        actual_buy_price=375000,
    )

    client, _ = staff_client
    with patch("apps.quotes.ai_pricing.requests.post", return_value=_gemini_ok()) as post:
        res = client.post(f"/api/v1/staff/requests/{current.request_code}/price-suggestion/")

    assert res.status_code == 200, res.content
    context = _prompt_context(post)
    assert context["similar_deals"][0]["actual_buy_price"] == 375000


@pytest.mark.django_db
@override_settings(GEMINI_API_KEY="test-key")
def test_price_suggestion_skips_the_model_without_comparables(staff_client, foreign_request):
    """Жиших хэлцэл байхгүй бол AI зохиохоос нь өмнө зогсооно."""
    client, _ = staff_client
    with patch("apps.quotes.ai_pricing.requests.post") as post:
        res = client.post(f"/api/v1/staff/requests/{foreign_request.request_code}/price-suggestion/")

    assert res.status_code == 200, res.content
    assert res.data["suggestion"] is None
    assert res.data["comparables_count"] == 0
    post.assert_not_called()


@pytest.mark.django_db
@override_settings(GEMINI_API_KEY="")
def test_price_suggestion_without_an_api_key_is_unavailable(staff_client, priced_request):
    client, _ = staff_client
    res = client.post(f"/api/v1/staff/requests/{priced_request.request_code}/price-suggestion/")
    assert res.status_code == 503
    assert "GEMINI_API_KEY" in res.data["detail"]


@pytest.mark.django_db
@override_settings(GEMINI_API_KEY="test-key")
def test_price_suggestion_reports_an_upstream_failure(staff_client, priced_request):
    client, _ = staff_client
    failed = Mock(status_code=429, text="rate limited")
    with patch("apps.quotes.ai_pricing.requests.post", return_value=failed):
        res = client.post(
            f"/api/v1/staff/requests/{priced_request.request_code}/price-suggestion/"
        )
    assert res.status_code == 502
    assert "429" in res.data["detail"]


@pytest.mark.django_db
@override_settings(GEMINI_API_KEY="test-key")
def test_price_suggestion_is_staff_only(auth_client, priced_request):
    client, _ = auth_client
    res = client.post(f"/api/v1/staff/requests/{priced_request.request_code}/price-suggestion/")
    assert res.status_code == 403

