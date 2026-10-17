from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.models import User
from apps.chat.models import Conversation
from apps.chat.services import post_message
from apps.notifications.models import PushDevice


def _expo_ok(*tickets):
    res = MagicMock()
    res.json.return_value = {"data": list(tickets) or [{"status": "ok"}]}
    return res


@pytest.fixture
def customer(db):
    return User.objects.create_user(email="cust@example.com", password="1234", full_name="Бат")


@pytest.fixture
def staff(db):
    return User.objects.create_user(email="op@ubpm.mn", password="1234", role=User.Role.ADMIN)


@pytest.mark.django_db
def test_customer_message_pushes_to_staff_with_unread_count(customer, staff):
    PushDevice.objects.create(user=staff, token="ExponentPushToken[staff]")
    PushDevice.objects.create(user=customer, token="ExponentPushToken[cust]")
    conv = Conversation.objects.create(customer=customer)

    with patch("apps.notifications.push.requests.post", return_value=_expo_ok()) as post:
        post_message(conv, customer, "Нэг")
        post_message(conv, customer, "Хоёр")

    sent = post.call_args.kwargs["json"]
    assert [n["to"] for n in sent] == ["ExponentPushToken[staff]"]
    assert sent[0]["title"] == "Бат"
    assert sent[0]["body"] == "Хоёр"
    assert sent[0]["badge"] == 2
    assert sent[0]["data"] == {"type": "chat", "conversation_id": conv.pk}


@pytest.mark.django_db
def test_staff_reply_pushes_only_to_that_customer(customer, staff):
    other = User.objects.create_user(email="other@example.com", password="1234")
    PushDevice.objects.create(user=customer, token="ExponentPushToken[cust]")
    PushDevice.objects.create(user=other, token="ExponentPushToken[other]")
    conv = Conversation.objects.create(customer=customer)

    with patch("apps.notifications.push.requests.post", return_value=_expo_ok()) as post:
        post_message(conv, staff, "Сайн байна уу")

    sent = post.call_args.kwargs["json"]
    assert [n["to"] for n in sent] == ["ExponentPushToken[cust]"]
    assert sent[0]["title"] == "UBPM"
    assert sent[0]["badge"] == 1


@pytest.mark.django_db
def test_unregistered_device_is_forgotten(customer, staff):
    PushDevice.objects.create(user=customer, token="ExponentPushToken[gone]")
    conv = Conversation.objects.create(customer=customer)
    dead = {"status": "error", "details": {"error": "DeviceNotRegistered"}}

    with patch("apps.notifications.push.requests.post", return_value=_expo_ok(dead)):
        post_message(conv, staff, "Сайн")

    assert not PushDevice.objects.exists()


@pytest.mark.django_db
def test_no_devices_means_no_request(customer):
    conv = Conversation.objects.create(customer=customer)
    with patch("apps.notifications.push.requests.post") as post:
        post_message(conv, customer, "Сайн")
    post.assert_not_called()


@pytest.mark.django_db
def test_push_failure_does_not_break_the_chat(customer, staff):
    import requests

    PushDevice.objects.create(user=staff, token="ExponentPushToken[staff]")
    conv = Conversation.objects.create(customer=customer)
    with patch(
        "apps.notifications.push.requests.post", side_effect=requests.ConnectionError("down")
    ):
        msg = post_message(conv, customer, "Сайн")
    assert msg.pk


# ---------- Дансны дугаар ----------


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["12", "5001234567", "MN50 0005 0050 1234 5678"])
def test_profile_form_saves_any_bank_account(client, customer, value):
    from django.urls import reverse

    client.force_login(customer)
    resp = client.post(
        reverse("accounts:profile"),
        {
            "full_name": "Бат",
            "phone": "99112233",
            "customer_type": "INDIVIDUAL",
            "bank_account": value,
        },
    )
    assert resp.status_code == 302, resp.context and resp.context["form"].errors
    customer.refresh_from_db()
    assert customer.bank_account == value
