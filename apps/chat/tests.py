import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.chat.models import Conversation, Message
from apps.chat.services import SEND_LIMIT_PER_MINUTE


@pytest.fixture
def customer(db):
    return User.objects.create_user(email="cust@example.com", password="1234", full_name="Бат")


@pytest.fixture
def staff(db):
    return User.objects.create_user(email="op@ubpm.mn", password="1234", role=User.Role.ADMIN)


def _send(client, conversation, body):
    return client.post(reverse("chat:send", args=[conversation.pk]), {"body": body})


@pytest.mark.django_db
def test_chat_needs_login(client):
    resp = client.get(reverse("chat:customer"))
    assert resp.status_code == 302
    assert resp["Location"].startswith(reverse("accounts:login"))


@pytest.mark.django_db
def test_customer_and_staff_talk_in_one_conversation(client, customer, staff):
    client.force_login(customer)
    assert client.get(reverse("chat:customer")).status_code == 200
    conv = Conversation.objects.get(customer=customer)

    resp = _send(client, conv, "  Сайн байна уу?  ")
    assert resp.status_code == 201
    assert resp.json()["message"]["body"] == "Сайн байна уу?"
    assert resp.json()["message"]["mine"] is True

    # Дахин нээхэд шинэ чат үүсэхгүй.
    client.get(reverse("chat:customer"))
    assert Conversation.objects.count() == 1

    client.force_login(staff)
    listing = client.get(reverse("chat:staff_list"))
    assert "Бат" in listing.content.decode()
    conv.refresh_from_db()
    assert conv.unread_for_staff

    client.get(reverse("chat:staff_thread", args=[conv.pk]))
    conv.refresh_from_db()
    assert not conv.unread_for_staff

    first_id = Message.objects.get().id
    assert _send(client, conv, "Сайн, юугаар туслах вэ?").status_code == 201

    client.force_login(customer)
    data = client.get(reverse("chat:poll", args=[conv.pk]), {"after": first_id}).json()
    assert [m["body"] for m in data["messages"]] == ["Сайн, юугаар туслах вэ?"]
    assert data["messages"][0]["from_staff"] is True
    assert data["messages"][0]["name"] == "UBPM"
    conv.refresh_from_db()
    assert not conv.unread_for_customer


@pytest.mark.django_db
def test_poll_returns_nothing_when_there_is_nothing_new(client, customer):
    client.force_login(customer)
    client.get(reverse("chat:customer"))
    conv = Conversation.objects.get()
    msg_id = _send(client, conv, "a").json()["message"]["id"]
    data = client.get(reverse("chat:poll", args=[conv.pk]), {"after": msg_id}).json()
    assert data == {"messages": []}


@pytest.mark.django_db
def test_customer_cannot_read_or_write_someone_elses_chat(client, customer):
    other = User.objects.create_user(email="other@example.com", password="1234")
    conv = Conversation.objects.create(customer=other)
    client.force_login(customer)
    assert client.get(reverse("chat:poll", args=[conv.pk])).status_code == 404
    assert _send(client, conv, "hi").status_code == 404
    assert client.get(reverse("chat:staff_list")).status_code == 302


@pytest.mark.django_db
def test_empty_long_and_flooding_messages_are_refused(client, customer):
    client.force_login(customer)
    client.get(reverse("chat:customer"))
    conv = Conversation.objects.get()
    assert _send(client, conv, "   ").status_code == 400
    assert _send(client, conv, "x" * 1001).status_code == 400
    for _ in range(SEND_LIMIT_PER_MINUTE):
        assert _send(client, conv, "hi").status_code == 201
    assert _send(client, conv, "hi").status_code == 429


@pytest.mark.django_db
def test_nav_shows_unread_badge(client, customer, staff):
    conv = Conversation.objects.create(customer=customer)
    client.force_login(customer)
    _send(client, conv, "Асуулт")

    client.force_login(staff)
    html = client.get(reverse("dashboard:overview")).content.decode()
    assert 'data-chat-badge class=' in html
    assert 'style="display:none">1<' not in html


@pytest.mark.django_db
def test_unread_endpoint_tracks_the_badge(client, customer, staff):
    conv = Conversation.objects.create(customer=customer)
    client.force_login(customer)
    _send(client, conv, "Асуулт")

    client.force_login(staff)
    assert client.get(reverse("chat:unread")).json() == {"count": 1}
    client.get(reverse("chat:staff_thread", args=[conv.pk]))
    assert client.get(reverse("chat:unread")).json() == {"count": 0}
    _send(client, conv, "Хариулт")

    client.force_login(customer)
    assert client.get(reverse("chat:unread")).json() == {"count": 1}
    html = client.get(reverse("accounts:my_requests")).content.decode()
    assert "data-chat-badge" in html


@pytest.mark.django_db
def test_unread_endpoint_needs_login(client):
    assert client.get(reverse("chat:unread")).status_code == 302


# ---------- Чат устгах ----------


@pytest.fixture
def busy_conversation(customer, staff):
    from apps.chat.services import post_message

    conv = Conversation.objects.create(customer=customer)
    post_message(conv, customer, "Сайн уу")
    post_message(conv, staff, "Сайн")
    return conv


@pytest.mark.django_db
def test_staff_deletes_a_chat_from_the_list(client, staff, busy_conversation):
    client.force_login(staff)
    resp = client.post(reverse("chat:staff_delete", args=[busy_conversation.pk]))
    assert resp.status_code == 302
    assert not Message.objects.exists()
    busy_conversation.refresh_from_db()
    assert busy_conversation.last_message_at is None
    assert list(client.get(reverse("chat:staff_list")).context["conversations"]) == []


@pytest.mark.django_db
def test_customer_keeps_chatting_after_the_chat_is_deleted(client, customer, staff, busy_conversation):
    """Хэрэглэгчийн нээлттэй чат ижил id-гаараа ажилласаар, дахин жагсаалтад гарна."""
    client.force_login(staff)
    client.post(reverse("chat:staff_delete", args=[busy_conversation.pk]))

    client.force_login(customer)
    assert _send(client, busy_conversation, "Дахин бичлээ").status_code == 201
    client.force_login(staff)
    assert "Бат" in client.get(reverse("chat:staff_list")).content.decode()


@pytest.mark.django_db
def test_customer_cannot_delete_a_chat(client, customer, busy_conversation):
    client.force_login(customer)
    client.post(reverse("chat:staff_delete", args=[busy_conversation.pk]))
    assert Message.objects.count() == 2


@pytest.mark.django_db
def test_chat_delete_needs_post(client, staff, busy_conversation):
    client.force_login(staff)
    resp = client.get(reverse("chat:staff_delete", args=[busy_conversation.pk]))
    assert resp.status_code == 405
    assert Message.objects.count() == 2
