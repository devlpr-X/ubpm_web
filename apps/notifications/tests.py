import importlib

import pytest
from django.conf import settings
from django.core import mail
from django.test import override_settings

from apps.intake.models import IntakeRequest
from apps.notifications.models import EmailLog
from apps.notifications.services import notify_new_request_customer, notify_quote_sent
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
