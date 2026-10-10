"""Хэрэглэгч ↔ админ чат.

Гацалтаас сэргийлж WebSocket ашиглахгүй — хуудас өөрөө хэдэн секунд тутам
зөвхөн `after=<сүүлийн id>`-ээс хойшхи шинэ мессежийг асууна (шинэ юм
байхгүй бол хариу нь хоосон жагсаалт). Хуудас нуугдсан үед асуухаа зогсоож,
идэвхгүй үед давтамжаа сааруулна — templates/chat/_thread.html.
"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.views import staff_required

from .models import MAX_MESSAGE_LENGTH, Conversation, Message

# Нэг удаад буцаах дээд хэмжээ — анх нээхэд сүүлийн N мессеж.
PAGE_SIZE = 50
# Спамаас: нэг хүн минутад үүнээс олон мессеж илгээхгүй.
SEND_LIMIT_PER_MINUTE = 20


def is_chat_staff(user):
    return user.is_superuser or user.is_staff_role


def _message_json(msg, viewer):
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


def _recent_messages(conversation, viewer):
    msgs = list(conversation.messages.select_related("sender").order_by("-id")[:PAGE_SIZE])
    msgs.reverse()
    return [_message_json(m, viewer) for m in msgs]


def _mark_read(conversation, viewer, upto_id):
    """Уншсан заагчийг урагшлуулна — шинэ мессеж байхгүй бол бичилт хийхгүй."""
    if not upto_id:
        return
    field = "staff_last_read_id" if is_chat_staff(viewer) else "customer_last_read_id"
    Conversation.objects.filter(pk=conversation.pk, **{f"{field}__lt": upto_id}).update(
        **{field: upto_id}
    )


def _conversation_for(request, conversation_id):
    """Ажилтан бүх чатыг, хэрэглэгч зөвхөн өөрийнхөө чатыг."""
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if not is_chat_staff(request.user) and conversation.customer_id != request.user.id:
        raise Http404
    return conversation


def _thread_page(request, template, conversation, **extra):
    messages = _recent_messages(conversation, request.user)
    if messages:
        _mark_read(conversation, request.user, messages[-1]["id"])
    return render(
        request,
        template,
        {"conversation": conversation, "initial_messages": messages, **extra},
    )


# --- Хуудсууд ---------------------------------------------------------------


@login_required
def customer_chat(request):
    if is_chat_staff(request.user):
        return redirect("chat:staff_list")
    conversation, _ = Conversation.objects.get_or_create(customer=request.user)
    return _thread_page(request, "chat/customer.html", conversation)


@staff_required
def staff_list(request):
    q = (request.GET.get("q") or "").strip()
    conversations = Conversation.objects.filter(last_message_at__isnull=False).select_related(
        "customer"
    )
    if q:
        conversations = conversations.filter(
            Q(customer__email__icontains=q)
            | Q(customer__full_name__icontains=q)
            | Q(customer__phone__icontains=q)
        )
    conversations = list(conversations[:200])
    # Сүүлийн мессежийн эхлэлийг жагсаалтад харуулна — бүгдийг нэг query-гээр.
    for c in conversations:
        c.last_id = max(c.last_customer_message_id, c.last_staff_message_id)
    last_by_id = Message.objects.in_bulk([c.last_id for c in conversations])
    for c in conversations:
        c.last_message = last_by_id.get(c.last_id)
    return render(request, "chat/staff_list.html", {"conversations": conversations, "q": q})


@staff_required
def staff_thread(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related("customer"), pk=conversation_id
    )
    customer = conversation.customer
    return _thread_page(
        request,
        "chat/staff_thread.html",
        conversation,
        customer=customer,
        customer_requests=customer.submitted_requests.order_by("-created_at")[:5],
    )


# --- JSON (polling) ---------------------------------------------------------


@login_required
@require_GET
def poll(request, conversation_id):
    conversation = _conversation_for(request, conversation_id)
    try:
        after = max(int(request.GET.get("after") or 0), 0)
    except ValueError:
        after = 0
    msgs = list(
        conversation.messages.filter(id__gt=after)
        .select_related("sender")
        .order_by("id")[:PAGE_SIZE]
    )
    if msgs:
        _mark_read(conversation, request.user, msgs[-1].id)
    return JsonResponse({"messages": [_message_json(m, request.user) for m in msgs]})


@login_required
@require_POST
def send(request, conversation_id):
    conversation = _conversation_for(request, conversation_id)
    body = (request.POST.get("body") or "").strip()
    if not body:
        return JsonResponse({"error": "Мессеж хоосон байна."}, status=400)
    if len(body) > MAX_MESSAGE_LENGTH:
        return JsonResponse(
            {"error": f"Мессеж {MAX_MESSAGE_LENGTH} тэмдэгтээс хэтрэхгүй."}, status=400
        )
    since = timezone.now() - timedelta(minutes=1)
    if (
        Message.objects.filter(sender=request.user, created_at__gte=since).count()
        >= SEND_LIMIT_PER_MINUTE
    ):
        return JsonResponse(
            {"error": "Хэт олон мессеж илгээлээ. Түр хүлээгээд дахин бичнэ үү."}, status=429
        )

    from_staff = is_chat_staff(request.user)
    with transaction.atomic():
        msg = Message.objects.create(
            conversation=conversation, sender=request.user, from_staff=from_staff, body=body
        )
        last_field = "last_staff_message_id" if from_staff else "last_customer_message_id"
        read_field = "staff_last_read_id" if from_staff else "customer_last_read_id"
        # Өөрийн бичсэнийг уншсан гэж тооцно.
        Conversation.objects.filter(pk=conversation.pk).update(
            last_message_at=msg.created_at, **{last_field: msg.id, read_field: msg.id}
        )
    return JsonResponse({"message": _message_json(msg, request.user)}, status=201)


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
