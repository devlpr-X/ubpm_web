"""Аппын push мэдэгдэл (Expo Push Service).

Апп нэвтрэх үедээ Expo push token-оо `/api/v1/push/devices/`-д бүртгэнэ
(PushDevice). Чатад мессеж ирэхэд нөгөө талын бүх төхөөрөмж рүү мэдэгдэл
илгээж, аппын дүрсэн дээрх тоог (badge) уншаагүй мессежийн тоогоор тавина.

Expo нь Android (FCM), iOS (APNs) хоёр руу өөрөө дамжуулдаг тул сервер талд
түлхүүр хэрэггүй — FCM/APNs-ийн тохиргоо EAS дээр хийгдэнэ.
"""

import logging
import re

import requests
from django.db.models import Q

from apps.accounts.models import User

from .models import PushDevice
from .services import _dispatch

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
# Expo нэг хүсэлтэд 100 хүртэл мэдэгдэл хүлээн авна.
CHUNK = 100
TOKEN_RE = re.compile(r"^Expo(nent)?PushToken\[[^\]]+\]$")
# Апп энэ нэртэй Android channel үүсгэдэг (дуу, чичиргээтэй).
CHAT_CHANNEL = "chat"


def is_expo_token(token):
    return bool(TOKEN_RE.fullmatch(token or ""))


def notify_chat_message(message):
    """Чатын шинэ мессежийн мэдэгдлийг commit болсны дараа background-д илгээнэ."""
    _dispatch(_send_chat_push, message.pk)


def _send_chat_push(message_id):
    from apps.chat.models import Message
    from apps.chat.services import staff_unread_messages, unread_messages_for

    msg = (
        Message.objects.select_related("conversation", "conversation__customer", "sender")
        .filter(pk=message_id)
        .first()
    )
    if msg is None:
        return
    conversation = msg.conversation
    body = msg.body if len(msg.body) <= 150 else msg.body[:149] + "…"
    data = {"type": "chat", "conversation_id": conversation.pk}

    if msg.from_staff:
        # Ажилтан → хэрэглэгч: зөвхөн тэр хэрэглэгчийн төхөөрөмжүүд.
        unread = unread_messages_for(conversation.customer)
        tokens = PushDevice.objects.filter(user=conversation.customer_id).values_list(
            "token", flat=True
        )
        title = "UBPM"
    else:
        # Хэрэглэгч → ажилтан: бүх ажилтны төхөөрөмж, тоо нь бүх чатын нийлбэр.
        unread = staff_unread_messages()
        tokens = PushDevice.objects.filter(
            Q(user__role__in=User.STAFF_ROLES) | Q(user__is_superuser=True),
            user__is_active=True,
        ).values_list("token", flat=True)
        customer = conversation.customer
        title = customer.full_name or customer.email

    send_push(
        [
            {
                "to": token,
                "title": title,
                "body": body,
                "data": data,
                "sound": "default",
                "badge": unread,
                "channelId": CHAT_CHANNEL,
                "priority": "high",
            }
            for token in tokens
        ]
    )


def send_push(notifications):
    """Expo руу илгээнэ; "DeviceNotRegistered" буцсан token-ыг устгана."""
    for start in range(0, len(notifications), CHUNK):
        chunk = notifications[start : start + CHUNK]
        try:
            res = requests.post(
                EXPO_PUSH_URL,
                json=chunk,
                headers={"Accept": "application/json"},
                timeout=10,
            )
            res.raise_for_status()
            tickets = res.json().get("data", [])
        except (requests.RequestException, ValueError):
            logger.exception("Expo push илгээхэд алдаа гарлаа")
            continue
        dead = [
            note["to"]
            for note, ticket in zip(chunk, tickets, strict=False)
            if ticket.get("status") == "error"
            and (ticket.get("details") or {}).get("error") == "DeviceNotRegistered"
        ]
        if dead:
            PushDevice.objects.filter(token__in=dead).delete()
