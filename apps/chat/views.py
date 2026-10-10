"""Хэрэглэгч ↔ админ чат (вэб).

Гацалтаас сэргийлж WebSocket ашиглахгүй — хуудас өөрөө хэдэн секунд тутам
зөвхөн `after=<сүүлийн id>`-ээс хойшхи шинэ мессежийг асууна (шинэ юм
байхгүй бол хариу нь хоосон жагсаалт). Хуудас нуугдсан үед асуухаа зогсоож,
идэвхгүй үед давтамжаа сааруулна — templates/chat/_thread.html.
Логик нь services.py-д (аппын API ч мөн түүнийг ашиглана).
"""

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.views import staff_required

from .models import Conversation
from .services import (
    ChatError,
    can_access,
    is_chat_staff,
    message_json,
    messages_after,
    post_message,
    recent_messages,
    staff_conversations,
    unread_count_for,
)


def _conversation_for(request, conversation_id):
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if not can_access(request.user, conversation):
        raise Http404
    return conversation


def _thread_page(request, template, conversation, **extra):
    return render(
        request,
        template,
        {
            "conversation": conversation,
            "initial_messages": recent_messages(conversation, request.user),
            **extra,
        },
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
    return render(
        request, "chat/staff_list.html", {"conversations": staff_conversations(q), "q": q}
    )


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
    return JsonResponse(
        {"messages": messages_after(conversation, request.user, request.GET.get("after"))}
    )


@login_required
@require_POST
def send(request, conversation_id):
    conversation = _conversation_for(request, conversation_id)
    try:
        msg = post_message(conversation, request.user, request.POST.get("body"))
    except ChatError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
    return JsonResponse({"message": message_json(msg, request.user)}, status=201)


@login_required
@require_GET
def unread(request):
    """Цэсний улаан тоог хуудас дахин ачаалалгүйгээр шинэчлэхэд (base.html)."""
    return JsonResponse({"count": unread_count_for(request.user)})
