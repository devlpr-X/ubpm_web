"""Email явуулах helper-үүд. Бүх send-ийг EmailLog-д бичнэ."""

import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import connections, transaction
from django.template.loader import render_to_string

from apps.accounts.models import User

from .models import EmailLog

logger = logging.getLogger(__name__)


def _dispatch(fn, *args, **kwargs):
    """Мэдэгдлийг transaction commit болсны ДАРАА background thread-д илгээнэ.

    SMTP сервер удаан/хүрэхгүй үед хэрэглэгчийн хүсэлт блоклогдож worker
    timeout-оор унадаг байсныг сэргийлнэ. EMAIL_ASYNC=False үед (тест)
    шууд синхроноор ажиллана.
    """
    if not getattr(settings, "EMAIL_ASYNC", True):
        fn(*args, **kwargs)
        return

    def _run():
        try:
            fn(*args, **kwargs)
        except Exception:  # noqa: BLE001
            logger.exception("Background мэдэгдэл илгээхэд алдаа гарлаа")
        finally:
            connections.close_all()

    transaction.on_commit(lambda: threading.Thread(target=_run, daemon=True).start())


def undeliverable_reason():
    """Захиа хүргэгдэхгүй тохиргоог илрүүлнэ (prod дээрх console fallback).

    EMAIL_HOST_USER/PASSWORD тохируулагдаагүй үед prod нь console backend руу
    шилждэг. Тэр backend дээр `msg.send()` алдаагүй өнгөрдөг тул EmailLog
    "амжилттай" гэж бичигдээд, үнэндээ хэнд ч хүрдэггүй — админ дээр бүх зүйл
    хэвийн харагдаж, асуудлыг олоход маш хэцүү болгодог.

    locmem-ийг оруулаагүй: Django тестийн үед түүн рүү сольдог бөгөөд тэнд
    mail.outbox шалгагддаг тул хүргэгдсэнд тооцно.
    """
    if settings.DEBUG:
        return ""
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if "console" in backend or "dummy" in backend:
        return (
            "EMAIL_BACKEND нь SMTP биш (console) тул захиа хэнд ч хүрээгүй. "
            "Railway → Variables дээр EMAIL_HOST_USER болон EMAIL_HOST_PASSWORD-ийг "
            "тохируулаад дахин deploy хийнэ үү."
        )
    return ""


def _build_site_url(path):
    """Сайтын бүтэн хаяг — SITE_URL тохируулагдаагүй бол host-оос дүгнэнэ."""
    site_url = getattr(settings, "SITE_URL", "")
    if site_url:
        return f"{site_url.rstrip('/')}{path}"

    try:
        domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else "localhost:8000"
    except (IndexError, AttributeError):
        domain = "localhost:8000"
    if domain in {"*", ""}:
        domain = "localhost:8000"
    return f"http://{domain}{path}"


def _build_tracking_url(intake_request):
    return _build_site_url(intake_request.public_tracking_url())


def admin_notify_email():
    """Бүх мэдэгдлийн хуулбар очих админ хайрцаг (хоосон бол хуулбар илгээхгүй)."""
    return (getattr(settings, "ADMIN_NOTIFY_EMAIL", "") or "").strip()


def _admin_bcc(recipient):
    """Админ хайрцгийг BCC болгон нэмнэ — хүлээн авагч нь өөрөө биш л бол."""
    admin = admin_notify_email()
    if admin and admin.lower() != (recipient or "").lower():
        return [admin]
    return []


def send_template_email(*, recipient, subject, template_base, context, intake_request=None):
    """`template_base` = template file нэр (.html, .txt suffix-гүй).

    HTML + plain text хоёр хувилбарыг дамжуулан илгээнэ. Мэдэгдэл бүрийн
    хуулбар ADMIN_NOTIFY_EMAIL рүү BCC-ээр давхар очно."""
    if not recipient:
        logger.warning("send_template_email: recipient хоосон, орхив")
        return False

    html = render_to_string(f"emails/{template_base}.html", context)
    try:
        text = render_to_string(f"emails/{template_base}.txt", context)
    except Exception:
        # plain text template байхгүй бол HTML-ээс strip хийнэ
        from django.utils.html import strip_tags

        text = strip_tags(html)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
        bcc=_admin_bcc(recipient),
    )
    msg.attach_alternative(html, "text/html")

    error = ""
    try:
        msg.send(fail_silently=False)
        success = True
    except Exception as exc:  # noqa: BLE001
        success = False
        error = str(exc)
        logger.exception("Email явуулахад алдаа гарлаа: %s", recipient)

    # send() амжилттай ч backend нь хаана ч хүргэдэггүй бол үүнийг амжилт гэж
    # бүртгэхгүй — эс бөгөөс тохиргооны алдаа админ дээр харагдахгүй өнгөрнө.
    if success:
        blocked = undeliverable_reason()
        if blocked:
            success = False
            error = blocked
            logger.error("Email хүргэгдэхгүй тохиргоо: %s — %s", recipient, blocked)

    EmailLog.objects.create(
        recipient_email=recipient,
        subject=subject,
        template_name=template_base,
        context_json={k: str(v) for k, v in context.items() if not _is_obj(v)},
        intake_request=intake_request,
        success=success,
        error=error,
    )
    return success


def _is_obj(v):
    """JSON-д шууд хадгалагдах боломжгүй object-ийг хайна."""
    return hasattr(v, "_meta") or hasattr(v, "objects")


def send_account_locked_email(user, code):
    """Хэт олон буруу оролдлогын дараа бүртгэл хаагдсаныг мэдэгдэж, кодыг нь илгээх.

    Хаалтыг тайлах цорын ганц хурдан зам нь энэ код тул захиандаа шууд оруулж
    өгнө — хэрэглэгч шуудангаа нээгээд кодоо бичихэд л шинэ PIN тавьж чадна.
    """
    if not user.email:
        return False
    return send_template_email(
        recipient=user.email,
        subject="UBPM — Бүртгэл түр хаагдлаа",
        template_base="account_locked",
        context={
            "code": code,
            "full_name": user.full_name or user.email,
            "attempts": getattr(settings, "ACCOUNT_LOCKOUT_MAX_ATTEMPTS", 5),
            "minutes": getattr(settings, "ACCOUNT_LOCKOUT_MINUTES", 30),
            "ttl_minutes": getattr(settings, "PASSWORD_RESET_CODE_TTL_MINUTES", 15),
            "reset_url": _build_site_url("/accounts/password-reset/verify/"),
        },
    )


def send_password_reset_code_email(user, code):
    """Нууц үг сэргээх 4 оронтой кодыг хэрэглэгчийн email рүү илгээх."""
    if not user.email:
        return False
    return send_template_email(
        recipient=user.email,
        subject="UBPM — Нууц үг сэргээх код",
        template_base="password_reset_code",
        context={
            "code": code,
            "full_name": user.full_name or user.email,
            "ttl_minutes": getattr(settings, "PASSWORD_RESET_CODE_TTL_MINUTES", 15),
        },
    )


# ----- Үйл явдлын handler-ууд -----


def notify_new_request_customer(intake):
    """Хүсэлт амжилттай үүссэн → submitter-д баталгаажуулах email."""
    _dispatch(_notify_new_request_customer, intake)


def _notify_new_request_customer(intake):
    if not intake.contact_email:
        return
    send_template_email(
        recipient=intake.contact_email,
        subject=f"UBPM — Хүсэлт {intake.request_code} хүлээн авлаа",
        template_base="request_received_customer",
        context={
            "request_obj": intake,
            "tracking_url": _build_tracking_url(intake),
            "request_code": intake.request_code,
            "contact_name": intake.contact_name,
        },
        intake_request=intake,
    )


def notify_new_request_staff(intake):
    """Шинэ хүсэлт → branch-ийн ажилтнуудад мэдэгдэл."""
    _dispatch(_notify_new_request_staff, intake)


def _notify_new_request_staff(intake):
    staff_qs = User.objects.filter(
        role__in=[User.Role.OPERATOR, User.Role.MANAGER, User.Role.ADMIN], is_active=True
    )
    if intake.preferred_branch_id:
        # branch-тэй холбоотой ажилтнуудад нэн тэргүүнд
        branch_staff = staff_qs.filter(branch=intake.preferred_branch)
        if branch_staff.exists():
            staff_qs = branch_staff

    emails = [u.email for u in staff_qs if u.email]
    # Ажилтан бүртгэгдээгүй (эсвэл и-мэйлгүй) байсан ч шинэ хүсэлт админ
    # хайрцаг руу заавал очих ёстой.
    if not emails and admin_notify_email():
        emails = [admin_notify_email()]

    for email in emails:
        send_template_email(
            recipient=email,
            subject=f"UBPM — Шинэ хүсэлт {intake.request_code}",
            template_base="new_request_staff",
            context={
                "request_obj": intake,
                "request_code": intake.request_code,
                "contact_name": intake.contact_name,
                "contact_phone": intake.contact_phone,
                "branch": intake.preferred_branch.name if intake.preferred_branch else "—",
                "items_count": intake.items.count(),
            },
            intake_request=intake,
        )


def notify_status_changed(intake, old_status, new_status, comment=""):
    """Submitter-д статусын өөрчлөлт мэдэгдэх."""
    _dispatch(_notify_status_changed, intake, old_status, new_status, comment)


def _notify_status_changed(intake, old_status, new_status, comment=""):
    if not intake.contact_email:
        return
    send_template_email(
        recipient=intake.contact_email,
        subject=f"UBPM — {intake.request_code} статус: {intake.get_status_display()}",
        template_base="status_changed",
        context={
            "request_obj": intake,
            "request_code": intake.request_code,
            "old_status": old_status,
            "new_status": new_status,
            "new_status_display": intake.get_status_display(),
            "comment": comment,
            "tracking_url": _build_tracking_url(intake),
        },
        intake_request=intake,
    )


def notify_quote_sent(quotation):
    """Үнэ санал илгээгдсэн → submitter-д email."""
    _dispatch(_notify_quote_sent, quotation)


def _notify_quote_sent(quotation):
    intake = quotation.intake_request
    if not intake.contact_email:
        return
    send_template_email(
        recipient=intake.contact_email,
        subject=f"UBPM — {intake.request_code}-н үнэ санал",
        template_base="quote_sent",
        context={
            "request_obj": intake,
            "request_code": intake.request_code,
            "quote": quotation,
            "min_price": quotation.quoted_price_min,
            "max_price": quotation.quoted_price_max,
            "valid_until": quotation.valid_until,
            "note": quotation.note,
            "tracking_url": _build_tracking_url(intake),
        },
        intake_request=intake,
    )


def notify_pickup_scheduled(pickup):
    """Pickup товлогдсон → submitter + assigned staff."""
    _dispatch(_notify_pickup_scheduled, pickup)


def _notify_pickup_scheduled(pickup):
    intake = pickup.intake_request
    recipients = []
    if intake.contact_email:
        recipients.append(intake.contact_email)
    if pickup.assigned_staff and pickup.assigned_staff.email:
        recipients.append(pickup.assigned_staff.email)

    for r in recipients:
        send_template_email(
            recipient=r,
            subject=f"UBPM — Pickup товлогдсон ({intake.request_code})",
            template_base="pickup_scheduled",
            context={
                "request_obj": intake,
                "request_code": intake.request_code,
                "pickup": pickup,
                "pickup_date": pickup.pickup_date,
                "pickup_address": pickup.pickup_address,
                "assigned_staff": pickup.assigned_staff.full_name
                if pickup.assigned_staff
                else "",
            },
            intake_request=intake,
        )
