"""Нэвтрэх оролдлогыг тоолох signal receiver-ууд.

`authenticate()`-ийн ирмэг дээр суудаг тул вэб, Django admin, мобайл API (JWT)
гурвуулаа ижил хамгаалалтад орно.
"""

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .backends import resolve_login_email
from .services import clear_login_lock, register_failed_login


@receiver(user_login_failed)
def count_failed_login(sender, credentials=None, **kwargs):
    creds = credentials or {}
    email = resolve_login_email(creds.get("username") or creds.get("email"))
    if email:
        register_failed_login(email)


@receiver(user_logged_in)
def reset_failed_login_counter(sender, user, **kwargs):
    clear_login_lock(user)
