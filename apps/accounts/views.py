import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView, FormView, ListView, UpdateView

from apps.intake.models import IntakeRequest

from .forms import (
    CustomerSignupForm,
    EmailLoginForm,
    PasswordResetRequestForm,
    PasswordResetVerifyForm,
    ProfileForm,
)
from .google import (
    GoogleAuthError,
    build_authorization_url,
    exchange_code_for_id_token,
    get_or_create_google_user,
    new_state_and_nonce,
    verify_google_id_token,
    web_login_configured,
)
from .models import User
from .services import reset_password_with_code, send_reset_code


def _post_login_url(user):
    """Нэвтэрсний дараа хаашаа явах вэ — ажилтан бол dashboard, үгүй бол хүсэлтүүд."""
    return reverse("dashboard:overview" if user.is_staff_role else "accounts:my_requests")


class UbpmLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return _post_login_url(self.request.user)


class UbpmLogoutView(LogoutView):
    next_page = reverse_lazy("core:home")


def _safe_next(request, raw):
    """`next` нь зөвхөн энэ сайт руу заасан үед хүчинтэй (open redirect-ээс сэргийлнэ)."""
    if raw and url_has_allowed_host_and_scheme(
        raw, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return raw
    return ""


def _callback_uri(request):
    """Google-д бүртгүүлсэн redirect URI. Хоёр талдаа ижил байх ёстой."""
    return request.build_absolute_uri(reverse("accounts:google_callback"))


class GoogleStartView(View):
    """Хэрэглэгчийг Google-ийн зөвшөөрлийн хуудас руу явуулна.

    Сонгодог authorization-code урсгал: бүтэн хуудсаар шилждэг тул iframe,
    popup, гуравдагч талын cookie-нээс хамаарахгүй.
    """

    def get(self, request):
        if not web_login_configured():
            messages.error(request, "Google-ээр нэвтрэх тохиргоо дутуу байна.")
            return redirect("accounts:login")

        state, nonce = new_state_and_nonce()
        request.session["google_oauth_state"] = state
        request.session["google_oauth_nonce"] = nonce
        request.session["google_oauth_next"] = _safe_next(request, request.GET.get("next"))

        return redirect(build_authorization_url(_callback_uri(request), state, nonce))


class GoogleCallbackView(View):
    """Google-оос буцаж ирэх цэг — `code`-г солиод сесс нээнэ."""

    def get(self, request):
        state = request.GET.get("state") or ""
        expected = request.session.pop("google_oauth_state", "")
        nonce = request.session.pop("google_oauth_nonce", "")
        next_url = request.session.pop("google_oauth_next", "")

        if request.GET.get("error"):
            # Хэрэглэгч "Cancel" дарсан бол ч энд ирнэ — алдаа гэж заахгүй.
            messages.info(request, "Google-ээр нэвтрэх үйлдэл цуцлагдлаа.")
            return redirect("accounts:login")

        # `state` нь сессэд хадгалсантай таарахгүй бол хүсэлт өөр газраас ирсэн.
        # Байтаар харьцуулна — compare_digest нь ASCII бус мөрөнд алдаа шиддэг,
        # харин `state`-г гаднаас дурын тэмдэгттэй илгээж болно.
        if not expected or not secrets.compare_digest(state.encode(), expected.encode()):
            messages.error(request, "Нэвтрэх хүсэлтийн баталгаа зөрлөө. Дахин оролдоно уу.")
            return redirect("accounts:login")

        code = request.GET.get("code") or ""
        if not code:
            messages.error(request, "Google-ийн хариу дутуу байна.")
            return redirect("accounts:login")

        try:
            id_token = exchange_code_for_id_token(code, _callback_uri(request))
            info = verify_google_id_token(id_token)
        except GoogleAuthError as exc:
            messages.error(request, str(exc))
            return redirect("accounts:login")

        # Токен нь ЭНЭ хүсэлтэд зориулагдсан эсэх (дахин тоглуулахаас хамгаална).
        if nonce and info.get("nonce") != nonce:
            messages.error(request, "Google-ийн хариу энэ хүсэлтэд тохирохгүй байна.")
            return redirect("accounts:login")

        user, created = get_or_create_google_user(info)
        # Google-ээр баталгаажсан тул нууц үг шалгах шаардлагагүй. Backend-ийг
        # тохиргооноос авна: Django сесст бичигдсэн замыг дараагийн хүсэлт бүр
        # дээр AUTHENTICATION_BACKENDS-тэй тулгадаг, жагсаалтад байхгүй бол
        # хэрэглэгчийг чимээгүйхэн ачаалахаа больж, нэвтрээгүй мэт харагдана.
        login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
        messages.success(
            request,
            "Тавтай морил! Бүртгэл амжилттай үүслээ." if created else "Амжилттай нэвтэрлээ.",
        )
        return redirect(next_url or _post_login_url(user))


class CustomerSignupView(CreateView):
    template_name = "accounts/signup.html"
    form_class = CustomerSignupForm
    success_url = reverse_lazy("accounts:my_requests")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, "Тавтай морил! Бүртгэл амжилттай үүслээ.")
        return response


class PasswordResetRequestView(FormView):
    """Step 1: email a 4-digit reset code."""

    template_name = "accounts/password_reset.html"
    form_class = PasswordResetRequestForm

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        send_reset_code(email)
        self.request.session["pw_reset_email"] = email
        messages.success(
            self.request, "Хэрэв энэ и-мэйл бүртгэлтэй бол баталгаажуулах код илгээлээ."
        )
        return redirect("accounts:password_reset_verify")


class PasswordResetVerifyView(FormView):
    """Step 2: verify the code and set a new 4-digit PIN."""

    template_name = "accounts/password_reset_verify.html"
    form_class = PasswordResetVerifyForm
    success_url = reverse_lazy("accounts:login")

    def get_initial(self):
        return {"email": self.request.session.get("pw_reset_email", "")}

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            reset_password_with_code(data["email"], data["code"], data["new_password1"])
        except ValidationError as exc:
            form.add_error("code", exc.messages[0])
            return self.form_invalid(form)
        self.request.session.pop("pw_reset_email", None)
        messages.success(
            self.request, "Нууц үг шинэчлэгдлээ. Шинэ PIN-ээрээ нэвтэрнэ үү."
        )
        return super().form_valid(form)


class ProfileView(LoginRequiredMixin, UpdateView):
    template_name = "accounts/profile.html"
    form_class = ProfileForm
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Профайл шинэчлэгдлээ.")
        return super().form_valid(form)


class MyRequestsView(LoginRequiredMixin, ListView):
    template_name = "accounts/my_requests.html"
    context_object_name = "requests"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        # Зочин үед оруулсан хүсэлтийг ч мөн ижил email-аар нь холбоно
        qs = IntakeRequest.objects.filter(
            Q(submitted_by=user) | Q(contact_email__iexact=user.email)
        )
        return qs.distinct().order_by("-created_at")


def role_required(*allowed_roles):
    """Decorator: зөвхөн заасан role-той хэрэглэгч хандана."""

    def decorator(view_func):
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in allowed_roles and not request.user.is_superuser:
                messages.error(request, "Энэ хуудсыг үзэх эрхгүй.")
                return redirect("core:home")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def staff_required(view_func):
    """Decorator alias: ADMIN/MANAGER/OPERATOR."""
    return role_required(User.Role.ADMIN, User.Role.MANAGER, User.Role.OPERATOR)(view_func)
