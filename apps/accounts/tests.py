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
# Вэб дээр Google-ээр нэвтрэх / шууд бүртгүүлэх
# ---------------------------------------------------------------------------
import json  # noqa: E402
from unittest.mock import patch  # noqa: E402

from django.test import override_settings  # noqa: E402

WEB_CLIENT_ID = "web-client-id.apps.googleusercontent.com"


def _google_payload(email="shine@example.com", name="Шинэ Хэрэглэгч", verified=True):
    return {
        "iss": "https://accounts.google.com",
        "aud": WEB_CLIENT_ID,
        "email": email,
        "email_verified": verified,
        "name": name,
    }


def _post_credential(client, next_url=None):
    body = {"credential": "fake-token"}
    if next_url is not None:
        body["next"] = next_url
    return client.post(
        reverse("accounts:google_login"),
        data=json.dumps(body),
        content_type="application/json",
    )


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=[WEB_CLIENT_ID])
@pytest.mark.django_db
def test_google_web_login_creates_account_and_signs_in(client):
    with patch(
        "apps.accounts.google.google_id_token.verify_oauth2_token",
        return_value=_google_payload(),
    ):
        res = _post_credential(client)

    assert res.status_code == 200, res.content
    body = res.json()
    assert body["created"] is True
    assert body["redirect"] == reverse("accounts:my_requests")

    user = User.objects.get(email="shine@example.com")
    assert user.role == User.Role.CUSTOMER
    assert user.full_name == "Шинэ Хэрэглэгч"
    # Нууц үг тавиагүй — зөвхөн Google-ээр нэвтэрнэ.
    assert not user.has_usable_password()
    # Сесс нээгдсэн эсэх.
    assert client.session["_auth_user_id"] == str(user.pk)


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=[WEB_CLIENT_ID])
@pytest.mark.django_db
def test_google_web_login_links_existing_account(client):
    existing = User.objects.create_user(
        email="huuchin@example.com", password="1234", full_name="Хуучин"
    )
    with patch(
        "apps.accounts.google.google_id_token.verify_oauth2_token",
        return_value=_google_payload(email="huuchin@example.com"),
    ):
        res = _post_credential(client)

    assert res.status_code == 200
    assert res.json()["created"] is False
    assert User.objects.filter(email="huuchin@example.com").count() == 1
    assert client.session["_auth_user_id"] == str(existing.pk)
    # Байгаа нэрийг Google-ийнхээр дарж бичихгүй.
    existing.refresh_from_db()
    assert existing.full_name == "Хуучин"


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=[WEB_CLIENT_ID])
@pytest.mark.django_db
def test_google_web_login_sends_staff_to_dashboard(client):
    User.objects.create_user(
        email="ops@ubpm.mn", password="1234", role=User.Role.OPERATOR
    )
    with patch(
        "apps.accounts.google.google_id_token.verify_oauth2_token",
        return_value=_google_payload(email="ops@ubpm.mn"),
    ):
        res = _post_credential(client)

    assert res.json()["redirect"] == reverse("dashboard:overview")


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=[WEB_CLIENT_ID])
@pytest.mark.django_db
def test_google_web_login_rejects_wrong_audience(client):
    payload = _google_payload()
    payload["aud"] = "someone-elses-client-id"
    with patch(
        "apps.accounts.google.google_id_token.verify_oauth2_token", return_value=payload
    ):
        res = _post_credential(client)

    assert res.status_code == 401
    assert not User.objects.filter(email="shine@example.com").exists()
    assert "_auth_user_id" not in client.session


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=[WEB_CLIENT_ID])
@pytest.mark.django_db
def test_google_web_login_rejects_unverified_email(client):
    with patch(
        "apps.accounts.google.google_id_token.verify_oauth2_token",
        return_value=_google_payload(verified=False),
    ):
        res = _post_credential(client)

    assert res.status_code == 401
    assert not User.objects.filter(email="shine@example.com").exists()


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=[])
@pytest.mark.django_db
def test_google_web_login_requires_server_config(client):
    res = _post_credential(client)
    assert res.status_code == 401
    assert "тохируулагдаагүй" in res.json()["error"]


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=[WEB_CLIENT_ID])
@pytest.mark.django_db
def test_google_web_login_ignores_offsite_next(client):
    """`next` нь гадаад сайт руу заавал үл тоомсорлоно (open redirect)."""
    with patch(
        "apps.accounts.google.google_id_token.verify_oauth2_token",
        return_value=_google_payload(),
    ):
        res = _post_credential(client, next_url="https://evil.example.com/steal")

    assert res.json()["redirect"] == reverse("accounts:my_requests")


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=[WEB_CLIENT_ID])
@pytest.mark.django_db
def test_google_web_login_honours_local_next(client):
    with patch(
        "apps.accounts.google.google_id_token.verify_oauth2_token",
        return_value=_google_payload(),
    ):
        res = _post_credential(client, next_url="/request/new/")

    assert res.json()["redirect"] == "/request/new/"


@override_settings(GOOGLE_OAUTH_WEB_CLIENT_ID=WEB_CLIENT_ID)
@pytest.mark.django_db
def test_login_page_shows_google_button(client):
    html = client.get(reverse("accounts:login")).content.decode()
    assert WEB_CLIENT_ID in html
    assert "accounts.google.com/gsi/client" in html


@override_settings(GOOGLE_OAUTH_WEB_CLIENT_ID="")
@pytest.mark.django_db
def test_login_page_hides_google_button_when_unconfigured(client):
    html = client.get(reverse("accounts:login")).content.decode()
    assert "accounts.google.com/gsi/client" not in html
