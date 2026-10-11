"""Чатын логик — вэбийн хуудас (views.py) болон аппын API (apps/api) хоёулаа ашиглана."""

from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import MAX_MESSAGE_LENGTH, Conversation, Message

# Нэг удаад буцаах дээд хэмжээ — анх нээхэд сүүлийн N мессеж.
PAGE_SIZE = 50
# Спамаас: нэг хүн минутад үүнээс олон мессеж илгээхгүй.
SEND_LIMIT_PER_MINUTE = 20


class ChatError(Exception):
    """Мессеж илгээж болохгүй үед — `status` нь HTTP код."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def is_chat_staff(user):
    return user.is_superuser or user.is_staff_role


def can_access(user, conversation):
    """Ажилтан бүх чатыг, хэрэглэгч зөвхөн өөрийнхөө чатыг."""
    return is_chat_staff(user) or conversation.customer_id == user.id


def message_json(msg, viewer):
    if msg.from_staff:
        name = "UBPM"
    else:
        sender = msg.sender
        name = (sender.full_name or sender.email) if sender else "Хэрэглэгч"
    return {
        "id": msg.id,
        "body": msg.body,
        "from_staff": msg.from_staff,
        "mine": msg.sender_id == viewer.id,
        "name": name,
        "created_at": msg.created_at.isoformat(),
    }


def mark_read(conversation, viewer, upto_id):
    """Уншсан заагчийг урагшлуулна — шинэ мессеж байхгүй бол бичилт хийхгүй."""
    if not upto_id:
        return
    field = "staff_last_read_id" if is_chat_staff(viewer) else "customer_last_read_id"
    Conversation.objects.filter(pk=conversation.pk, **{f"{field}__lt": upto_id}).update(
        **{field: upto_id}
    )


def recent_messages(conversation, viewer):
    """Сүүлийн PAGE_SIZE мессеж (хуучнаас шинэ рүү), уншсанд тооцно."""
    msgs = list(conversation.messages.select_related("sender").order_by("-id")[:PAGE_SIZE])
    msgs.reverse()
    if msgs:
        mark_read(conversation, viewer, msgs[-1].id)
    return [message_json(m, viewer) for m in msgs]


def messages_after(conversation, viewer, after):
    """`after` id-ээс хойшхи шинэ мессежүүд, уншсанд тооцно."""
    try:
        after = max(int(after or 0), 0)
    except (TypeError, ValueError):
        after = 0
    msgs = list(
        conversation.messages.filter(id__gt=after)
        .select_related("sender")
        .order_by("id")[:PAGE_SIZE]
    )
    if msgs:
        mark_read(conversation, viewer, msgs[-1].id)
    return [message_json(m, viewer) for m in msgs]


def post_message(conversation, sender, body):
    body = (body or "").strip()
    if not body:
        raise ChatError("Мессеж хоосон байна.")
    if len(body) > MAX_MESSAGE_LENGTH:
        raise ChatError(f"Мессеж {MAX_MESSAGE_LENGTH} тэмдэгтээс хэтрэхгүй.")
    since = timezone.now() - timedelta(minutes=1)
    if (
        Message.objects.filter(sender=sender, created_at__gte=since).count()
        >= SEND_LIMIT_PER_MINUTE
    ):
        raise ChatError("Хэт олон мессеж илгээлээ. Түр хүлээгээд дахин бичнэ үү.", status=429)

    from_staff = is_chat_staff(sender)
    with transaction.atomic():
        msg = Message.objects.create(
            conversation=conversation, sender=sender, from_staff=from_staff, body=body
        )
        last_field = "last_staff_message_id" if from_staff else "last_customer_message_id"
        read_field = "staff_last_read_id" if from_staff else "customer_last_read_id"
        # Өөрийн бичсэнийг уншсан гэж тооцно.
        Conversation.objects.filter(pk=conversation.pk).update(
            last_message_at=msg.created_at, **{last_field: msg.id, read_field: msg.id}
        )
        # Нөгөө тал руу push мэдэгдэл (апп) — commit болсны дараа background-д.
        from apps.notifications.push import notify_chat_message

        notify_chat_message(msg)
    return msg


def clear_conversation(conversation):
    """Ажилтан чатыг бүхэлд нь устгана — бүх мессеж арилж, жагсаалтаас гарна.

    Conversation мөр нь өөрөө үлдэнэ: хэрэглэгчийн нээлттэй чат (вэб/апп) ижил
    id-гаараа үргэлжлэн ажиллаж, дахин бичвэл жагсаалтад шинээр гарч ирнэ.
    """
    with transaction.atomic():
        conversation.messages.all().delete()
        Conversation.objects.filter(pk=conversation.pk).update(
            last_message_at=None,
            last_customer_message_id=0,
            last_staff_message_id=0,
            customer_last_read_id=0,
            staff_last_read_id=0,
        )


def staff_conversations(q="", limit=200):
    """Ажилтны жагсаалт — сүүлийн мессежийг `last_message`-д нэг query-гээр."""
    conversations = Conversation.objects.filter(last_message_at__isnull=False).select_related(
        "customer"
    )
    q = (q or "").strip()
    if q:
        conversations = conversations.filter(
            Q(customer__email__icontains=q)
            | Q(customer__full_name__icontains=q)
            | Q(customer__phone__icontains=q)
        )
    conversations = list(conversations[:limit])
    for c in conversations:
        c.last_id = max(c.last_customer_message_id, c.last_staff_message_id)
    last_by_id = Message.objects.in_bulk([c.last_id for c in conversations])
    for c in conversations:
        c.last_message = last_by_id.get(c.last_id)
    return conversations


def staff_unread_messages():
    """Ажилтнууд нэг уншсан заагчтай тул бүх чатын уншаагүй мессежийн нийлбэр."""
    return Message.objects.filter(
        from_staff=False, id__gt=F("conversation__staff_last_read_id")
    ).count()


def unread_messages_for(user):
    """Уншаагүй мессежийн тоо — аппын дүрс, табын тэмдэглэгээ, push-ийн badge."""
    if not user.is_authenticated:
        return 0
    if is_chat_staff(user):
        return staff_unread_messages()
    return Message.objects.filter(
        conversation__customer=user,
        from_staff=True,
        id__gt=F("conversation__customer_last_read_id"),
    ).count()


def unread_count_for(user):
    """Цэсний тэмдэглэгээнд: ажилтанд уншаагүй чатын тоо, хэрэглэгчид 0 эсвэл 1."""
    if not user.is_authenticated:
        return 0
    if is_chat_staff(user):
        return Conversation.objects.filter(
            last_customer_message_id__gt=F("staff_last_read_id")
        ).count()
    return Conversation.objects.filter(
        customer=user, last_staff_message_id__gt=F("customer_last_read_id")
    ).count()
