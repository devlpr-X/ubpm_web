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
        email="op@x.com", password="1234", full_name="Оператор", role=User.Role.OPERATOR
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
    User.objects.create_user(email="ops@ubpm.mn", password="1234", role=User.Role.OPERATOR)
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
