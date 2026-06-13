from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, ListView, UpdateView

from apps.intake.models import IntakeRequest

from .forms import (
    CustomerSignupForm,
    EmailLoginForm,
    PasswordResetRequestForm,
    PasswordResetVerifyForm,
    ProfileForm,
)
from .models import User
from .services import reset_password_with_code, send_reset_code


class UbpmLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if user.is_staff_role:
            return reverse_lazy("dashboard:overview")
        return reverse_lazy("accounts:my_requests")


class UbpmLogoutView(LogoutView):
    next_page = reverse_lazy("core:home")


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
