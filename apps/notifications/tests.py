import importlib

import pytest
from django.conf import settings
from django.core import mail
from django.test import override_settings

from apps.intake.models import IntakeRequest
from apps.notifications.models import EmailLog
from apps.notifications.services import (
    notify_new_request_customer,
    notify_new_request_staff,
    notify_quote_sent,
)
from apps.quotes.models import Quotation


@pytest.mark.django_db
def test_notify_new_request_customer_sends_and_logs():
    r = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", contact_email="x@y.com"
    )
    notify_new_request_customer(r)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["x@y.com"]
    assert EmailLog.objects.filter(intake_request=r, success=True).count() == 1


@pytest.mark.django_db
def test_no_email_when_customer_has_no_email():
    r = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    notify_new_request_customer(r)
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(DEFAULT_FROM_EMAIL="UBPM <ubpm.service@gmail.com>")
def test_quote_email_sent_from_configured_address():
    """Үнийн санал ажилтны хаягаас биш, тохируулсан нэг хаягаас явна."""
    r = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", contact_email="x@y.com"
    )
    quote = Quotation.objects.create(
        intake_request=r, quoted_price_min=100000, quoted_price_max=200000
    )

    notify_quote_sent(quote)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].from_email == settings.DEFAULT_FROM_EMAIL
    assert mail.outbox[0].message()["From"] == "UBPM <ubpm.service@gmail.com>"


def test_prod_pins_from_address_to_the_smtp_account(monkeypatch):
    """Gmail нь нэвтэрсэн бүртгэлээсээ өөр From-ыг зөвшөөрдөггүй тул prod дээр
    From хаяг үргэлж EMAIL_HOST_USER болно."""
    monkeypatch.setenv("SECRET_KEY", "x" * 50)
    monkeypatch.setenv("EMAIL_HOST_USER", "ubpm.service@gmail.com")
    monkeypatch.setenv("EMAIL_HOST_PASSWORD", "app-password")

    from ubpm.settings import prod

    importlib.reload(prod)

    assert prod.DEFAULT_FROM_EMAIL.endswith("<ubpm.service@gmail.com>")
    assert prod.SERVER_EMAIL == prod.DEFAULT_FROM_EMAIL
    assert prod.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"


CONSOLE_BACKEND = "django.core.mail.backends.console.EmailBackend"


@pytest.mark.django_db
@override_settings(DEBUG=False, EMAIL_BACKEND=CONSOLE_BACKEND)
def test_console_backend_in_prod_is_logged_as_failure():
    """Prod дээр console backend руу унасан бол амжилт гэж бүртгэхгүй.

    Console backend дээр send() алдаагүй өнгөрдөг тул өмнө нь EmailLog
    "амжилттай" гэж бичигдээд, захиа хэнд ч хүрдэггүй байсан.
    """
    r = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", contact_email="x@y.com"
    )
    notify_new_request_customer(r)

    log = EmailLog.objects.get(intake_request=r)
    assert log.success is False
    assert "EMAIL_HOST_USER" in log.error


@pytest.mark.django_db
@override_settings(DEBUG=True, EMAIL_BACKEND=CONSOLE_BACKEND)
def test_console_backend_in_dev_stays_successful():
    """Хөгжүүлэлтийн үед console backend хэвийн — алдаа гэж тэмдэглэхгүй."""
    r = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", contact_email="x@y.com"
    )
    notify_new_request_customer(r)
    assert EmailLog.objects.get(intake_request=r).success is True


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_smtp_backend_still_reports_success():
    """Тестийн locmem backend нь хүргэдэгт тооцогдоно (mail.outbox шалгагддаг)."""
    r = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", contact_email="x@y.com"
    )
    notify_new_request_customer(r)
    assert len(mail.outbox) == 1
    assert EmailLog.objects.get(intake_request=r).success is True


# ---------------------------------------------------------------------------
# Resend (HTTP API) backend — Railway дээр SMTP порт хаалттай үеийн суваг
# ---------------------------------------------------------------------------
RESEND_BACKEND = "apps.notifications.backends.ResendEmailBackend"


class _FakeResponse:
    def __init__(self, status_code=200, text='{"id":"abc"}'):
        self.status_code = status_code
        self.text = text


@override_settings(EMAIL_BACKEND=RESEND_BACKEND, RESEND_API_KEY="re_test_key")
@pytest.mark.django_db
def test_resend_backend_posts_html_and_text(monkeypatch):
    """Мэдэгдэл нь HTML + plain text хоёуланг API руу дамжуулна."""
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeResponse()

    monkeypatch.setattr("apps.notifications.backends.requests.post", fake_post)

    r = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", contact_email="x@y.com"
    )
    notify_new_request_customer(r)

    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_test_key"
    body = captured["json"]
    assert body["to"] == ["x@y.com"]
    assert r.request_code in body["subject"]
    assert body["html"] and body["text"]
    assert EmailLog.objects.get(intake_request=r).success is True


@override_settings(EMAIL_BACKEND=RESEND_BACKEND, RESEND_API_KEY="re_test_key")
@pytest.mark.django_db
def test_resend_api_error_is_recorded(monkeypatch):
    """API-ийн татгалзал EmailLog дээр яг шалтгаантайгаа бичигдэнэ."""
    monkeypatch.setattr(
        "apps.notifications.backends.requests.post",
        lambda *a, **kw: _FakeResponse(403, '{"message":"domain is not verified"}'),
    )

    r = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", contact_email="x@y.com"
    )
    notify_new_request_customer(r)

    log = EmailLog.objects.get(intake_request=r)
    assert log.success is False
    assert "403" in log.error
    assert "domain is not verified" in log.error


@override_settings(EMAIL_BACKEND=RESEND_BACKEND, RESEND_API_KEY="")
@pytest.mark.django_db
def test_resend_without_api_key_is_recorded_as_failure():
    r = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", contact_email="x@y.com"
    )
    notify_new_request_customer(r)

    log = EmailLog.objects.get(intake_request=r)
    assert log.success is False
    assert "RESEND_API_KEY" in log.error


@pytest.mark.django_db
def test_prod_prefers_resend_over_smtp(monkeypatch):
    """RESEND_API_KEY байвал SMTP-ийн оронд түүнийг сонгоно."""
    monkeypatch.setenv("SECRET_KEY", "x" * 50)
    monkeypatch.setenv("EMAIL_HOST_USER", "ubpm.service@gmail.com")
    monkeypatch.setenv("EMAIL_HOST_PASSWORD", "app-password")
    monkeypatch.setenv("RESEND_API_KEY", "re_live_key")

    from ubpm.settings import prod

    importlib.reload(prod)

    assert prod.EMAIL_BACKEND == RESEND_BACKEND
    # Resend үед From хаягийг EMAIL_HOST_USER руу албадан солихгүй — Resend нь
    # баталгаажуулсан домайны хаягийг шаарддаг тул солих нь илгээлтийг эвдэнэ.
    assert "ubpm.service@gmail.com" not in prod.DEFAULT_FROM_EMAIL


# ---------------------------------------------------------------------------
# Админ хайрцаг — бүх мэдэгдлийн хуулбар
# ---------------------------------------------------------------------------
ADMIN_BOX = "ubpm.mn@gmail.com"


@pytest.mark.django_db
@override_settings(ADMIN_NOTIFY_EMAIL=ADMIN_BOX)
def test_every_notification_is_copied_to_the_admin_inbox():
    r = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", contact_email="x@y.com"
    )
    notify_new_request_customer(r)
    assert mail.outbox[0].to == ["x@y.com"]
    assert mail.outbox[0].bcc == [ADMIN_BOX]


@pytest.mark.django_db
@override_settings(ADMIN_NOTIFY_EMAIL=ADMIN_BOX)
def test_admin_is_not_bcced_on_their_own_mail():
    r = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", contact_email=ADMIN_BOX
    )
    notify_new_request_customer(r)
    assert mail.outbox[0].bcc == []


@pytest.mark.django_db
@override_settings(ADMIN_NOTIFY_EMAIL="")
def test_copy_can_be_switched_off():
    r = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", contact_email="x@y.com"
    )
    notify_new_request_customer(r)
    assert mail.outbox[0].bcc == []


@pytest.mark.django_db
@override_settings(ADMIN_NOTIFY_EMAIL=ADMIN_BOX)
def test_new_request_reaches_the_admin_when_no_staff_exists():
    """Ажилтан бүртгэгдээгүй ч шинэ хүсэлт админ хайрцаг руу очно."""
    r = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    notify_new_request_staff(r)
    assert [m.to for m in mail.outbox] == [[ADMIN_BOX]]
