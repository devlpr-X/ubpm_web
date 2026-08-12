from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.core import mail
from django.urls import reverse

from apps.accounts.models import User
from apps.intake.models import IntakeRequest


@pytest.fixture
def staff(db):
    u = User.objects.create_user(
        email="op@x.com", password="pw1234", role=User.Role.OPERATOR, is_staff=True
    )
    return u


@pytest.fixture
def authed(client, staff):
    client.login(email="op@x.com", password="pw1234")
    return client


@pytest.mark.django_db
def test_dashboard_pages(authed):
    r = IntakeRequest.objects.create(contact_name="X", contact_phone="9911")
    assert authed.get(reverse("dashboard:overview")).status_code == 200
    assert authed.get(reverse("dashboard:request_list")).status_code == 200
    assert authed.get(reverse("dashboard:pickup_list")).status_code == 200
    assert authed.get(reverse("dashboard:reports")).status_code == 200
    assert authed.get(reverse("dashboard:request_detail", args=[r.request_code])).status_code == 200


@pytest.mark.django_db
def test_export_csv(authed):
    IntakeRequest.objects.create(contact_name="X", contact_phone="9911")
    resp = authed.get(reverse("dashboard:export") + "?format=csv")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")


@pytest.mark.django_db
def test_export_xlsx(authed):
    IntakeRequest.objects.create(contact_name="X", contact_phone="9911")
    resp = authed.get(reverse("dashboard:export"))
    assert resp.status_code == 200
    assert "spreadsheetml" in resp["Content-Type"]


@pytest.mark.django_db
def test_change_status_creates_history(authed):
    r = IntakeRequest.objects.create(contact_name="X", contact_phone="9911")
    resp = authed.post(
        reverse("dashboard:change_status", args=[r.request_code]),
        {"new_status": IntakeRequest.Status.PRICE_SENT, "comment": "test"},
    )
    assert resp.status_code == 302
    r.refresh_from_db()
    assert r.status == IntakeRequest.Status.PRICE_SENT
    assert r.history.count() == 1


@pytest.mark.django_db
def test_anonymous_redirect_from_dashboard(client):
    resp = client.get(reverse("dashboard:overview"))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_resending_a_quote_overwrites_the_existing_one(authed):
    """Хүсэлт тутамд ганц үнэ санал — дахин илгээвэл хуучин нь шинэчлэгдэнэ."""
    r = IntakeRequest.objects.create(
        contact_name="X", contact_phone="9911", contact_email="c@x.mn"
    )
    url = reverse("dashboard:add_quote", args=[r.request_code])

    authed.post(url, {"quoted_price_min": "100000", "quoted_price_max": "200000", "note": "эхний"})
    assert r.quotes.count() == 1

    authed.post(url, {"quoted_price_min": "300000", "quoted_price_max": "400000", "note": "хоёр дахь"})

    assert r.quotes.count() == 1
    quote = r.quotes.get()
    assert quote.quoted_price_min == Decimal("300000")
    assert quote.quoted_price_max == Decimal("400000")
    assert quote.note == "хоёр дахь"
    # Санал нэг ч, илгээх бүрт хэрэглэгч захиа авна.
    quote_mails = [m for m in mail.outbox if "үнэ санал" in m.subject]
    assert len(quote_mails) == 2


@pytest.mark.django_db
def test_quote_success_message_shows_the_recipient(authed):
    r = IntakeRequest.objects.create(
        contact_name="X", contact_phone="9911", contact_email="hereglegch@x.mn"
    )
    resp = authed.post(
        reverse("dashboard:add_quote", args=[r.request_code]),
        {"quoted_price_min": "100000", "quoted_price_max": "200000"},
        follow=True,
    )
    text = " ".join(str(m) for m in get_messages(resp.wsgi_request))
    assert "hereglegch@x.mn" in text


@pytest.mark.django_db
def test_quote_warns_when_customer_has_no_email(authed):
    r = IntakeRequest.objects.create(contact_name="X", contact_phone="9911")
    resp = authed.post(
        reverse("dashboard:add_quote", args=[r.request_code]),
        {"quoted_price_min": "100000", "quoted_price_max": "200000"},
        follow=True,
    )
    text = " ".join(str(m) for m in get_messages(resp.wsgi_request))
    assert "имэйл хаяг үлдээгээгүй" in text
    assert len(mail.outbox) == 0
