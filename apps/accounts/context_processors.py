"""Нэвтрэлттэй холбоотой template context."""

from django.conf import settings


def google_signin(request):
    """Google-ээр нэвтрэх товчид хэрэгтэй Web client ID.

    Хоосон бол `_google_button.html` товчийг огт зурахгүй — тохируулаагүй үед
    хэрэглэгч дарж байгаад алдаа авахаас сэргийлнэ.
    """
    return {"google_client_id": settings.GOOGLE_OAUTH_WEB_CLIENT_ID}
