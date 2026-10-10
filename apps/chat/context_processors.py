from .services import unread_count_for


def chat_unread(request):
    """Цэсэн дэх «Чат»-ын уншаагүй тэмдэглэгээ (нэвтрээгүй бол query хийхгүй)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"chat_unread": 0}
    return {"chat_unread": unread_count_for(user)}
