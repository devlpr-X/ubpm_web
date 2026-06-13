import pytest
from django.core import mail

from apps.intake.models import IntakeRequest
from apps.notifications.models import EmailLog
from apps.notifications.services import notify_new_request_customer


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
