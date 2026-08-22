from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import PasswordResetCode, User
from apps.accounts.services import reset_password_with_code


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
    op = User.objects.create_user(email="op@x.com", password="x", role=User.Role.ADMIN)
    cust = User.objects.create_user(email="c@x.com", password="x")
    assert op.is_staff_role
    assert not cust.is_staff_role


@pytest.mark.django_db
def test_login_redirects_staff_to_dashboard(client):
    User.objects.create_user(
        email="op@x.com", password="pw1234", role=User.Role.ADMIN, is_staff=True
    )
    resp = client.post(
        reverse("accounts:login"),
        {"username": "op@x.com", "password": "pw1234"},
        follow=False,
    )
    assert resp.status_code == 302
    assert "dashboard" in resp.url


# ---------------------------------------------------------------------------
# Холбоо барих мэдээлэл — профайл ↔ хүсэлт
# ---------------------------------------------------------------------------
def test_customer_type_choices_match_intake():
    """Профайл ба хүсэлтийн хоорондох утгууд яг таарч байх ёстой (шууд хуулагддаг)."""
    from apps.intake.models import IntakeRequest

    assert User.CustomerType.choices == IntakeRequest.CustomerType.choices


@pytest.mark.django_db
def test_contact_initial_prefills_from_profile():
    from apps.accounts.contact import contact_initial

    user = User.objects.create_user(
        email="c@x.com",
        password="1234",
        full_name="Бат",
        phone="99110011",
        city="Дархан",
        district="1-р баг",
    )
    initial = contact_initial(user)
    assert initial["contact_name"] == "Бат"
    assert initial["contact_phone"] == "99110011"
    assert initial["contact_email"] == "c@x.com"
    assert initial["city"] == "Дархан"
    assert initial["district"] == "1-р баг"


@pytest.mark.django_db
def test_contact_initial_is_empty_for_guests():
    from django.contrib.auth.models import AnonymousUser

    from apps.accounts.contact import contact_initial

    assert contact_initial(AnonymousUser()) == {}
    assert contact_initial(None) == {}


@pytest.mark.django_db
def test_save_contact_to_profile_fills_then_updates():
    from apps.accounts.contact import save_contact_to_profile
    from apps.intake.models import IntakeRequest

    user = User.objects.create_user(email="c@x.com", password="1234")
    first = IntakeRequest.objects.create(
        contact_name="Бат", contact_phone="99110011", city="Улаанбаатар", district="ХУД"
    )
    save_contact_to_profile(user, first)
    user.refresh_from_db()
    assert (user.full_name, user.phone, user.district) == ("Бат", "99110011", "ХУД")

    # Дараагийн хүсэлт дээр өөрчилсөн утга профайлд шинэчлэгдэнэ.
    second = IntakeRequest.objects.create(
        contact_name="Бат", contact_phone="88220022", city="Улаанбаатар", district=""
    )
    save_contact_to_profile(user, second)
    user.refresh_from_db()
    assert user.phone == "88220022"
    # Хоосон утга хуучин мэдээллийг дардаггүй.
    assert user.district == "ХУД"


@pytest.mark.django_db
def test_save_contact_to_profile_never_touches_login_email():
    from apps.accounts.contact import save_contact_to_profile
    from apps.intake.models import IntakeRequest

    user = User.objects.create_user(email="login@x.com", password="1234")
    intake = IntakeRequest.objects.create(
        contact_name="Бат", contact_phone="99110011", contact_email="other@x.com"
    )
    save_contact_to_profile(user, intake)
    user.refresh_from_db()
    assert user.email == "login@x.com"


@pytest.mark.django_db
def test_profile_form_requires_company_name_for_companies(client):
    User.objects.create_user(email="c@x.com", password="1234")
    client.login(username="c@x.com", password="1234")
    url = reverse("accounts:profile")

    resp = client.post(url, {"full_name": "Бат", "customer_type": "COMPANY"})
    assert resp.status_code == 200
    assert resp.context["form"].errors["company_name"]

    resp = client.post(
        url, {"full_name": "Бат", "customer_type": "COMPANY", "company_name": "ХХК"}
    )
    assert resp.status_code == 302
    assert User.objects.get(email="c@x.com").company_name == "ХХК"


@pytest.mark.django_db
def test_staff_profile_is_never_overwritten_by_a_request():
    """Оператор үйлчлүүлэгчийн өмнөөс хүсэлт үүсгэвэл өөрийнх нь профайл хэвээр."""
    from apps.accounts.contact import contact_initial, save_contact_to_profile
    from apps.intake.models import IntakeRequest

    op = User.objects.create_user(
        email="op@x.com", password="1234", full_name="Оператор", role=User.Role.ADMIN
    )
    intake = IntakeRequest.objects.create(contact_name="Үйлчлүүлэгч", contact_phone="99110011")

    assert save_contact_to_profile(op, intake) == []
    assert contact_initial(op) == {}
    op.refresh_from_db()
    assert op.full_name == "Оператор"
    assert op.phone == ""



# ---------------------------------------------------------------------------
# Вэб дээр Google-ээр нэвтрэх / шууд бүртгүүлэх (authorization-code redirect)
# ---------------------------------------------------------------------------
from unittest.mock import patch  # noqa: E402
from urllib.parse import parse_qs, urlparse  # noqa: E402

from django.test import override_settings  # noqa: E402

WEB_CLIENT_ID = "web-client-id.apps.googleusercontent.com"
google_configured = override_settings(
    GOOGLE_OAUTH_WEB_CLIENT_ID=WEB_CLIENT_ID,
    GOOGLE_OAUTH2_SECRET="test-secret",
    GOOGLE_OAUTH_CLIENT_IDS=[WEB_CLIENT_ID],
)


def _payload(email="shine@example.com", name="Шинэ Хэрэглэгч", nonce=None, verified=True):
    return {
        "iss": "https://accounts.google.com",
        "aud": WEB_CLIENT_ID,
        "email": email,
        "email_verified": verified,
        "name": name,
        "nonce": nonce,
    }


def _start(client, next_url=None):
    """Эхний алхам — Google руу шилжих. `state`/`nonce`-ыг буцаана."""
    url = reverse("accounts:google_login")
    if next_url:
        url += f"?next={next_url}"
    res = client.get(url)
    params = parse_qs(urlparse(res["Location"]).query)
    return res, params["state"][0], params["nonce"][0]


def _callback(client, state, payload):
    with patch("apps.accounts.views.exchange_code_for_id_token", return_value="tok"), patch(
        "apps.accounts.google.google_id_token.verify_oauth2_token", return_value=payload
    ):
        return client.get(reverse("accounts:google_callback"), {"code": "c", "state": state})


@google_configured
@pytest.mark.django_db
def test_google_start_redirects_to_google(client):
    res, state, nonce = _start(client)

    assert res.status_code == 302
    parsed = urlparse(res["Location"])
    assert parsed.netloc == "accounts.google.com"
    params = parse_qs(parsed.query)
    assert params["client_id"] == [WEB_CLIENT_ID]
    assert params["response_type"] == ["code"]
    assert params["redirect_uri"] == ["http://testserver/accounts/google/callback/"]
    # state/nonce нь сесст хадгалагдана.
    assert client.session["google_oauth_state"] == state
    assert client.session["google_oauth_nonce"] == nonce


@google_configured
@pytest.mark.django_db
def test_google_callback_creates_account_and_signs_in(client):
    _, state, nonce = _start(client)
    res = _callback(client, state, _payload(nonce=nonce))

    assert res.status_code == 302
    assert res["Location"] == reverse("accounts:my_requests")

    user = User.objects.get(email="shine@example.com")
    assert user.role == User.Role.CUSTOMER
    assert user.full_name == "Шинэ Хэрэглэгч"
    assert not user.has_usable_password()
    assert client.session["_auth_user_id"] == str(user.pk)


@google_configured
@pytest.mark.django_db
def test_google_session_survives_the_next_request(client):
    """Сесс бичигдэх нь хангалтгүй — дараагийн хүсэлт дээр нэвтэрсэн хэвээр байх ёстой.

    `login()`-д AUTHENTICATION_BACKENDS-д байхгүй backend дамжуулбал Django
    сессийг бичсэн ч дараагийн хүсэлт дээр хэрэглэгчийг ачаалахгүй өнгөрдөг.
    """
    _, state, nonce = _start(client)
    _callback(client, state, _payload(nonce=nonce))

    # Нэвтрэлт шаарддаг хуудас руу орвол login руу буцаахгүй байх ёстой.
    res = client.get(reverse("accounts:my_requests"))
    assert res.status_code == 200, "дараагийн хүсэлт дээр нэвтрэлт алдагдсан"
    assert res.context["user"].is_authenticated
    assert res.context["user"].email == "shine@example.com"


@google_configured
@pytest.mark.django_db
def test_google_account_gets_helpful_error_on_password_login(client):
    """Google-ээр үүссэн бүртгэлд нууц үгээр орох гэвэл шалтгааныг тайлбарлана."""
    _, state, nonce = _start(client)
    _callback(client, state, _payload(nonce=nonce))
    client.logout()

    res = client.post(
        reverse("accounts:login"),
        {"username": "shine@example.com", "password": "1234"},
    )
    assert res.status_code == 200
    assert "Google-ээр үүссэн" in res.content.decode()


@google_configured
@pytest.mark.django_db
def test_google_callback_links_existing_account(client):
    existing = User.objects.create_user(
        email="huuchin@example.com", password="1234", full_name="Хуучин"
    )
    _, state, nonce = _start(client)
    _callback(client, state, _payload(email="huuchin@example.com", nonce=nonce))

    assert User.objects.filter(email="huuchin@example.com").count() == 1
    assert client.session["_auth_user_id"] == str(existing.pk)
    existing.refresh_from_db()
    assert existing.full_name == "Хуучин"  # Google-ийн нэрээр дарж бичихгүй


@google_configured
@pytest.mark.django_db
def test_google_callback_sends_staff_to_dashboard(client):
    User.objects.create_user(email="ops@ubpm.mn", password="1234", role=User.Role.ADMIN)
    _, state, nonce = _start(client)
    res = _callback(client, state, _payload(email="ops@ubpm.mn", nonce=nonce))

    assert res["Location"] == reverse("dashboard:overview")


@google_configured
@pytest.mark.django_db
def test_google_callback_rejects_mismatched_state(client):
    """Өөр газраас ирсэн буцалт — CSRF хамгаалалт."""
    _, _, nonce = _start(client)
    res = _callback(client, "biш-state", _payload(nonce=nonce))

    assert res["Location"] == reverse("accounts:login")
    assert not User.objects.filter(email="shine@example.com").exists()
    assert "_auth_user_id" not in client.session


@google_configured
@pytest.mark.django_db
def test_google_callback_rejects_mismatched_nonce(client):
    _, state, _ = _start(client)
    res = _callback(client, state, _payload(nonce="өөр-nonce"))

    assert res["Location"] == reverse("accounts:login")
    assert not User.objects.filter(email="shine@example.com").exists()


@google_configured
@pytest.mark.django_db
def test_google_callback_rejects_wrong_audience(client):
    _, state, nonce = _start(client)
    payload = _payload(nonce=nonce)
    payload["aud"] = "someone-elses-client-id"
    res = _callback(client, state, payload)

    assert res["Location"] == reverse("accounts:login")
    assert not User.objects.filter(email="shine@example.com").exists()


@google_configured
@pytest.mark.django_db
def test_google_callback_rejects_unverified_email(client):
    _, state, nonce = _start(client)
    res = _callback(client, state, _payload(nonce=nonce, verified=False))

    assert res["Location"] == reverse("accounts:login")
    assert not User.objects.filter(email="shine@example.com").exists()


@google_configured
@pytest.mark.django_db
def test_google_callback_handles_user_cancelling(client):
    _, state, _ = _start(client)
    res = client.get(
        reverse("accounts:google_callback"), {"error": "access_denied", "state": state}
    )
    assert res["Location"] == reverse("accounts:login")


@google_configured
@pytest.mark.django_db
def test_google_login_honours_local_next(client):
    _, state, nonce = _start(client, next_url="/request/new/")
    res = _callback(client, state, _payload(nonce=nonce))
    assert res["Location"] == "/request/new/"


@google_configured
@pytest.mark.django_db
def test_google_login_ignores_offsite_next(client):
    _, state, nonce = _start(client, next_url="https://evil.example.com/steal")
    res = _callback(client, state, _payload(nonce=nonce))
    assert res["Location"] == reverse("accounts:my_requests")


@override_settings(GOOGLE_OAUTH_WEB_CLIENT_ID="", GOOGLE_OAUTH2_SECRET="")
@pytest.mark.django_db
def test_google_start_without_config_returns_to_login(client):
    res = client.get(reverse("accounts:google_login"))
    assert res["Location"] == reverse("accounts:login")


@google_configured
@pytest.mark.django_db
def test_login_page_shows_google_button(client):
    html = client.get(reverse("accounts:login")).content.decode()
    assert reverse("accounts:google_login") in html
    assert "Google-ээр үргэлжлүүлэх" in html


@override_settings(GOOGLE_OAUTH_WEB_CLIENT_ID="", GOOGLE_OAUTH2_SECRET="")
@pytest.mark.django_db
def test_login_page_hides_google_button_when_unconfigured(client):
    html = client.get(reverse("accounts:login")).content.decode()
    assert "Google-ээр үргэлжлүүлэх" not in html


# ---------------------------------------------------------------------------
# Нэвтрэх оролдлогын хязгаар (5 буруу PIN → бүртгэл хаагдана)
# ---------------------------------------------------------------------------
def _try_login(client, email, pin):
    return client.post(
        reverse("accounts:login"), {"username": email, "password": pin}, follow=False
    )


def _locked_user(client, email="lock@x.com", pin="1234"):
    """5 удаа буруу PIN оруулж бүртгэлийг хаалгана."""
    user = User.objects.create_user(email=email, password=pin)
    for _ in range(5):
        _try_login(client, email, "9999")
    user.refresh_from_db()
    return user


@pytest.mark.django_db
def test_wrong_pins_are_counted(client):
    user = User.objects.create_user(email="count@x.com", password="1234")
    _try_login(client, "count@x.com", "0000")
    _try_login(client, "count@x.com", "0000")
    user.refresh_from_db()
    assert user.failed_login_attempts == 2
    assert not user.is_login_locked


@pytest.mark.django_db
def test_successful_login_clears_the_counter(client):
    user = User.objects.create_user(email="ok@x.com", password="1234")
    for _ in range(4):
        _try_login(client, "ok@x.com", "0000")
    assert _try_login(client, "ok@x.com", "1234").status_code == 302
    user.refresh_from_db()
    assert user.failed_login_attempts == 0


@pytest.mark.django_db
def test_five_wrong_pins_lock_the_account(client):
    user = _locked_user(client)
    assert user.is_login_locked

    # Хаагдсаны дараа ЗӨВ нууц үг ч нэвтрүүлэхгүй — таамаглах оролдлого зогсоно.
    res = _try_login(client, "lock@x.com", "1234")
    assert res.status_code == 200
    assert "_auth_user_id" not in client.session
    assert "хаалаа" in res.content.decode()


@pytest.mark.django_db
def test_lockout_emails_a_reset_code(client):
    user = _locked_user(client, email="mail@x.com")
    locked_mail = mail.outbox[-1]
    code = PasswordResetCode.objects.filter(user=user).latest("created_at").code

    assert locked_mail.to == [user.email]
    assert "хаагдлаа" in locked_mail.subject
    assert code in locked_mail.body


@pytest.mark.django_db
def test_further_attempts_do_not_send_more_codes(client):
    user = _locked_user(client, email="spam@x.com")
    before = PasswordResetCode.objects.filter(user=user).count()
    for _ in range(3):
        _try_login(client, "spam@x.com", "8888")
    assert PasswordResetCode.objects.filter(user=user).count() == before


@pytest.mark.django_db
def test_reset_with_the_emailed_code_unlocks_the_account(client):
    user = _locked_user(client, email="back@x.com")
    code = PasswordResetCode.objects.filter(user=user).latest("created_at").code

    reset_password_with_code("back@x.com", code, "4321")

    user.refresh_from_db()
    assert not user.is_login_locked
    assert user.failed_login_attempts == 0
    assert _try_login(client, "back@x.com", "4321").status_code == 302


@pytest.mark.django_db
def test_lock_expires_after_the_configured_window(client, settings):
    user = _locked_user(client, email="wait@x.com")
    user.locked_until = timezone.now() - timedelta(minutes=1)
    user.save(update_fields=["locked_until"])

    assert not user.is_login_locked
    assert _try_login(client, "wait@x.com", "1234").status_code == 302


@pytest.mark.django_db
def test_api_login_says_the_account_is_locked():
    api = APIClient()
    User.objects.create_user(email="app@x.com", password="1234")
    for _ in range(4):
        api.post("/api/v1/auth/login/", {"email": "app@x.com", "password": "0000"}, format="json")

    res = api.post(
        "/api/v1/auth/login/", {"email": "app@x.com", "password": "0000"}, format="json"
    )
    assert res.status_code == 401
    assert res.data["code"] == "account_locked"


# ---------------------------------------------------------------------------
# Профайлын байршил (газрын зураг)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_request_location_is_saved_to_the_profile():
    from apps.accounts.contact import save_contact_to_profile
    from apps.intake.models import IntakeRequest

    user = User.objects.create_user(email="loc@x.com", password="1234")
    intake = IntakeRequest.objects.create(
        contact_name="Бат",
        contact_phone="99110011",
        pickup_required=True,
        pickup_lat="47.918800",
        pickup_lng="106.917600",
    )
    save_contact_to_profile(user, intake)

    user.refresh_from_db()
    assert user.has_pickup_location
    assert (str(user.pickup_lat), str(user.pickup_lng)) == ("47.918800", "106.917600")


@pytest.mark.django_db
def test_request_without_location_keeps_the_saved_point():
    """Байршилгүй хүсэлт профайл дээрх хуучин цэгийг арилгахгүй."""
    from apps.accounts.contact import save_contact_to_profile
    from apps.intake.models import IntakeRequest

    user = User.objects.create_user(
        email="keep@x.com", password="1234", pickup_lat="47.918800", pickup_lng="106.917600"
    )
    save_contact_to_profile(
        user, IntakeRequest.objects.create(contact_name="Бат", contact_phone="99110011")
    )

    user.refresh_from_db()
    assert user.has_pickup_location


@pytest.mark.django_db
def test_profile_page_shows_and_saves_the_map_point(client):
    User.objects.create_user(email="map@x.com", password="1234")
    client.login(username="map@x.com", password="1234")
    url = reverse("accounts:profile")

    resp = client.post(
        url,
        {
            "full_name": "Бат",
            "customer_type": "INDIVIDUAL",
            "pickup_lat": "47.900000",
            "pickup_lng": "106.900000",
        },
    )
    assert resp.status_code == 302

    user = User.objects.get(email="map@x.com")
    assert (str(user.pickup_lat), str(user.pickup_lng)) == ("47.900000", "106.900000")
    assert "profile-map" in client.get(url).content.decode()


@pytest.mark.django_db
def test_request_form_offers_the_saved_location(client):
    User.objects.create_user(
        email="offer@x.com", password="1234", pickup_lat="47.918800", pickup_lng="106.917600"
    )
    client.login(username="offer@x.com", password="1234")

    # `type` параметргүй үед эхлээд төрлөө сонгох дэлгэц гардаг.
    html = client.get(reverse("intake:request_new"), {"type": "broken"}).content.decode()
    assert "Профайлд хадгалсан байршлаа ашиглах" in html
    assert "47.918800" in html


@pytest.mark.django_db
def test_request_form_hides_the_option_without_a_saved_location(client):
    User.objects.create_user(email="none@x.com", password="1234")
    client.login(username="none@x.com", password="1234")

    html = client.get(reverse("intake:request_new"), {"type": "broken"}).content.decode()
    assert "Профайлд хадгалсан байршлаа ашиглах" not in html


# --- Миний хүсэлтүүд — хуудаслалт --------------------------------------------


def _make_requests(count, **kwargs):
    from apps.intake.models import IntakeRequest

    return [
        IntakeRequest.objects.create(contact_name=f"Хүсэлт {i}", contact_phone="99110011", **kwargs)
        for i in range(count)
    ]


@pytest.mark.django_db
def test_my_requests_paginates_at_ten(client):
    user = User.objects.create_user(email="c@x.com", password="1234")
    _make_requests(12, submitted_by=user)
    client.force_login(user)
    url = reverse("accounts:my_requests")

    page1 = client.get(url)
    assert page1.status_code == 200
    assert page1.context["is_paginated"] is True
    assert len(page1.context["requests"]) == 10
    assert page1.context["page_obj"].paginator.count == 12

    page2 = client.get(url, {"page": 2})
    assert len(page2.context["requests"]) == 2
    # Хуудсууд давхцахгүй — нийт 12 өөр хүсэлт.
    codes = {r.pk for r in page1.context["requests"]} | {r.pk for r in page2.context["requests"]}
    assert len(codes) == 12


@pytest.mark.django_db
def test_my_requests_shows_counter_and_page_links(client):
    user = User.objects.create_user(email="c@x.com", password="1234")
    _make_requests(25, submitted_by=user)
    client.force_login(user)

    body = client.get(reverse("accounts:my_requests"), {"page": 2}).content.decode()
    assert "11–20 / нийт 25 хүсэлт" in body
    assert "?page=1" in body and "?page=3" in body
    assert "Өмнөх" in body and "Дараах" in body


@pytest.mark.django_db
def test_my_requests_counter_shown_without_pagination(client):
    """Нэг хуудсанд багтсан ч нийт тоо харагдана (өмнө нь юу ч харагддаггүй байсан)."""
    user = User.objects.create_user(email="c@x.com", password="1234")
    _make_requests(3, submitted_by=user)
    client.force_login(user)

    body = client.get(reverse("accounts:my_requests")).content.decode()
    assert "1–3 / нийт 3 хүсэлт" in body
    assert "Дараах" not in body


@pytest.mark.django_db
def test_my_requests_elides_long_page_ranges(client):
    from django.core.paginator import Paginator

    user = User.objects.create_user(email="c@x.com", password="1234")
    _make_requests(120, submitted_by=user)  # 12 хуудас
    client.force_login(user)

    resp = client.get(reverse("accounts:my_requests"), {"page": 6})
    assert list(resp.context["page_range"]) == [
        1,
        Paginator.ELLIPSIS,
        5,
        6,
        7,
        Paginator.ELLIPSIS,
        12,
    ]
    assert "…" in resp.content.decode()


@pytest.mark.django_db
def test_my_requests_annotates_item_count(client):
    """Төхөөрөмжийн тоо annotate-аар ирнэ — мөр бүрт нэмэлт query явуулахгүй."""
    from apps.intake.models import DeviceCategory, DeviceItem

    user = User.objects.create_user(email="c@x.com", password="1234")
    category = DeviceCategory.objects.create(name="Гар утас", slug="phone")
    for req in _make_requests(5, submitted_by=user):
        DeviceItem.objects.create(intake_request=req, category=category)
        DeviceItem.objects.create(intake_request=req, category=category)

    client.force_login(user)
    resp = client.get(reverse("accounts:my_requests"))
    assert [r.item_count for r in resp.context["requests"]] == [2, 2, 2, 2, 2]
    assert "2 төхөөрөмж" in resp.content.decode()


@pytest.mark.django_db
def test_my_requests_still_includes_guest_requests_by_email(client):
    """Зочноор илгээсэн хүсэлт email-ээр холбогдсон хэвээр, тоологдоно."""
    user = User.objects.create_user(email="c@x.com", password="1234")
    _make_requests(2, submitted_by=user)
    _make_requests(3, contact_email="C@X.com")
    client.force_login(user)

    resp = client.get(reverse("accounts:my_requests"))
    assert resp.context["page_obj"].paginator.count == 5


@pytest.mark.django_db
def test_my_requests_out_of_range_page_shows_last_page(client):
    """Хүрээнээс хэтэрсэн ?page= үед 404 биш — жагсаалт алга болохгүй."""
    user = User.objects.create_user(email="c@x.com", password="1234")
    _make_requests(9, submitted_by=user)  # нэг хуудас
    client.force_login(user)
    url = reverse("accounts:my_requests")

    resp = client.get(url, {"page": 2})
    assert resp.status_code == 200
    assert len(resp.context["requests"]) == 9
    assert resp.context["page_obj"].number == 1


@pytest.mark.django_db
def test_my_requests_invalid_page_falls_back_to_first(client):
    user = User.objects.create_user(email="c@x.com", password="1234")
    _make_requests(25, submitted_by=user)
    client.force_login(user)
    url = reverse("accounts:my_requests")

    assert client.get(url, {"page": "хоёр"}).context["page_obj"].number == 1
    # Хэтэрхий том дугаар — сүүлийн хуудас.
    assert client.get(url, {"page": 99}).context["page_obj"].number == 3


# --- Role — Админ / Хэрэглэгч гэсэн 2 л эрх ------------------------------------


def test_only_two_roles_exist():
    assert [value for value, _label in User.Role.choices] == ["ADMIN", "CUSTOMER"]
    assert User.STAFF_ROLES == frozenset({User.Role.ADMIN})


@pytest.mark.django_db
def test_admin_is_staff_and_customer_is_not():
    admin = User.objects.create_user(email="a@x.com", password="x", role=User.Role.ADMIN)
    customer = User.objects.create_user(email="c@x.com", password="x")

    assert admin.is_staff_role
    assert customer.role == User.Role.CUSTOMER  # бүртгэл үргэлж хэрэглэгч үүсгэнэ
    assert not customer.is_staff_role


@pytest.mark.django_db
def test_dashboard_is_open_to_admins_and_closed_to_customers(client):
    url = reverse("dashboard:overview")

    User.objects.create_user(email="c@x.com", password="1234", role=User.Role.CUSTOMER)
    client.login(email="c@x.com", password="1234")
    assert client.get(url)["Location"] == reverse("core:home")
    client.logout()

    User.objects.create_user(email="a@x.com", password="1234", role=User.Role.ADMIN)
    client.login(email="a@x.com", password="1234")
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_migration_merges_the_old_staff_roles_into_admin():
    """0006_two_roles — хуучин Менежер/Оператор мөрүүд Админ болно."""
    import importlib

    from django.apps import apps as django_apps

    migration = importlib.import_module("apps.accounts.migrations.0006_two_roles")

    old = User.objects.create_user(email="op@x.com", password="x")
    User.objects.filter(pk=old.pk).update(role="OPERATOR")
    customer = User.objects.create_user(email="c@x.com", password="x")

    migration.merge_staff_roles(django_apps, None)

    old.refresh_from_db()
    customer.refresh_from_db()
    assert old.role == User.Role.ADMIN
    assert customer.role == User.Role.CUSTOMER
