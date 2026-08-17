"""Нэвтрэлттэй холбоотой template context."""

from .google import web_login_configured


def google_signin(request):
    """Google-ээр нэвтрэх товчийг харуулах эсэх.

    Client ID эсвэл secret дутуу бол товчийг огт зурахгүй — тохируулаагүй үед
    хэрэглэгч дарж байгаад алдаа авахаас сэргийлнэ.
    """
    return {"google_login_enabled": web_login_configured()}
