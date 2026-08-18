"""HTTP API-аар захиа илгээх Django email backend (Resend).

Яагаад SMTP биш вэ: Railway зэрэг hosting платформууд spam-аас сэргийлж гадагш
SMTP портуудыг (25/465/587) хаадаг. Тэр үед Gmail-ийн App Password хэдий зөв ч
холболт `[Errno 101] Network is unreachable` гэж унадаг. HTTPS (443) нээлттэй
тул HTTP API-аар илгээвэл асуудалгүй ажиллана.

Django-гийн стандарт backend интерфэйсийг хэрэгжүүлдэг тул `send_mail`,
`EmailMultiAlternatives` зэрэг бүх код өөрчлөлтгүйгээр ажиллана.
"""

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailBackend(BaseEmailBackend):
    """Resend-ийн HTTP API-аар захиа илгээнэ."""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = getattr(settings, "RESEND_API_KEY", "")
        self.timeout = getattr(settings, "EMAIL_TIMEOUT", 10)

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            if not self.fail_silently:
                raise ValueError(
                    "RESEND_API_KEY тохируулагдаагүй байна — захиа илгээх боломжгүй."
                )
            return 0

        sent = 0
        for message in email_messages:
            if self._send(message):
                sent += 1
        return sent

    def _payload(self, message):
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(message.to),
            "subject": message.subject,
        }
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)

        # Үндсэн бие: content_subtype нь "html" бол HTML, эс бөгөөс plain text.
        if getattr(message, "content_subtype", "plain") == "html":
            payload["html"] = message.body
        else:
            payload["text"] = message.body

        # EmailMultiAlternatives-ийн HTML хувилбар (мэдэгдлүүд үүнийг ашигладаг).
        for alternative in getattr(message, "alternatives", None) or []:
            content, mimetype = alternative[0], alternative[1]
            if mimetype == "text/html":
                payload["html"] = content

        return payload

    def _send(self, message):
        if not message.recipients():
            return False

        try:
            res = requests.post(
                RESEND_API_URL,
                json=self._payload(message),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        except requests.RequestException:
            if not self.fail_silently:
                raise
            return False

        if res.status_code >= 300:
            if not self.fail_silently:
                # Хариуг таслаж оруулна — EmailLog.error дээр яг шалтгаан харагдана
                # (ж: домайн баталгаажаагүй, API key буруу).
                raise RuntimeError(f"Resend API {res.status_code}: {res.text[:300]}")
            return False

        return True
