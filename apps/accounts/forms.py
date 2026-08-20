from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)
from django.contrib.auth.password_validation import validate_password

from .backends import resolve_login_email
from .models import User

INPUT_CLASS = "w-full rounded-md border border-gray-300 px-3 py-2"

# Shared widget attrs for a 4-digit numeric PIN input.
PIN_ATTRS = {
    "class": INPUT_CLASS + " text-center text-lg tracking-[0.5em]",
    "inputmode": "numeric",
    "pattern": "[0-9]*",
    "maxlength": "4",
    "autocomplete": "off",
    "placeholder": "••••",
}


class EmailLoginForm(AuthenticationForm):
    """Username field-ийг email-аар хэрэглэх AuthenticationForm wrapper."""

    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "autofocus": True,
                "class": INPUT_CLASS,
                "placeholder": "you@example.com",
                "inputmode": "email",
            }
        ),
    )
    password = forms.CharField(
        label="4 оронтой нууц үг (PIN)",
        widget=forms.PasswordInput(attrs=PIN_ATTRS),
    )

    def get_invalid_login_error(self):
        """Алдааны шалтгааныг тодорхой хэлнэ.

        Хаагдсан бүртгэл болон Google-ээр үүссэн (нууц үггүй) бүртгэлийг
        ялгаж заана — эс бөгөөс "Email эсвэл нууц үг буруу" гэж гарч,
        хэрэглэгч байхгүй нууц үгээ хайж эхэлдэг.
        """
        email = resolve_login_email(self.cleaned_data.get("username"))
        user = User.objects.filter(email__iexact=email).first() if email else None
        if user:
            if user.is_login_locked:
                return forms.ValidationError(
                    "Нууц үг хэт олон удаа буруу орлоо. Бүртгэлийг %(minutes)s минут "
                    "хаалаа. Таны и-мэйл рүү сэргээх код илгээсэн — «Нууц үг мартсан "
                    "уу?» холбоосоор орж кодоо оруулаад шинэ PIN тавивал шууд нэвтэрнэ.",
                    code="account_locked",
                    params={"minutes": user.lockout_minutes_left},
                )
            if not user.has_usable_password():
                return forms.ValidationError(
                    "Энэ бүртгэл Google-ээр үүссэн тул нууц үг байхгүй байна. "
                    "Доорх «Google-ээр үргэлжлүүлэх» товчоор нэвтэрнэ үү.",
                    code="google_only",
                )
        return super().get_invalid_login_error()


class CustomerSignupForm(UserCreationForm):
    full_name = forms.CharField(
        label="Бүтэн нэр",
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "w-full rounded-md border border-gray-300 px-3 py-2"}
        ),
    )
    phone = forms.CharField(
        label="Утас",
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full rounded-md border border-gray-300 px-3 py-2",
                "inputmode": "numeric",
            }
        ),
    )

    class Meta:
        model = User
        fields = ("email", "full_name", "phone", "password1", "password2")
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full rounded-md border border-gray-300 px-3 py-2",
                    "inputmode": "email",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "4 оронтой нууц үг (PIN)"
        self.fields["password2"].label = "Нууц үг давтах"
        for f in ("password1", "password2"):
            self.fields[f].widget = forms.PasswordInput(attrs=PIN_ATTRS)
            self.fields[f].help_text = ""

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CUSTOMER
        if commit:
            user.save()
        return user


class PasswordResetRequestForm(forms.Form):
    """Step 1: enter email to receive a 4-digit reset code."""

    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "autofocus": True,
                "class": INPUT_CLASS,
                "placeholder": "you@example.com",
                "inputmode": "email",
            }
        ),
    )


class PasswordResetVerifyForm(forms.Form):
    """Step 2: enter the emailed code and a new 4-digit PIN."""

    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "inputmode": "email"}),
    )
    code = forms.CharField(
        label="Баталгаажуулах код (4 орон)",
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS + " text-center text-lg tracking-[0.5em]",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
                "maxlength": "4",
                "autocomplete": "off",
                "placeholder": "0000",
            }
        ),
    )
    new_password1 = forms.CharField(
        label="Шинэ нууц үг (PIN)", widget=forms.PasswordInput(attrs=PIN_ATTRS)
    )
    new_password2 = forms.CharField(
        label="Шинэ нууц үг давтах", widget=forms.PasswordInput(attrs=PIN_ATTRS)
    )

    def clean_new_password1(self):
        pin = self.cleaned_data.get("new_password1")
        if pin:
            validate_password(pin)
        return pin

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("new_password1"), cleaned.get("new_password2")
        if p1 and p2 and p1 != p2:
            self.add_error("new_password2", "Нууц үг хоёр таарахгүй байна.")
        return cleaned


class ProfileForm(forms.ModelForm):
    """Холбоо барих мэдээлэл — хүсэлт илгээхэд маягт эндээс автоматаар дүүрнэ."""

    class Meta:
        model = User
        fields = (
            "full_name",
            "phone",
            "customer_type",
            "company_name",
            "city",
            "district",
            "address_line",
            # Газрын зургаас сонгосон цэг — доорх зураг дээр дарж тавина.
            "pickup_lat",
            "pickup_lng",
        )
        widgets = {
            "pickup_lat": forms.HiddenInput(),
            "pickup_lng": forms.HiddenInput(),
            "full_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric"}),
            "customer_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "company_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "city": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "district": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "address_line": forms.TextInput(attrs={"class": INPUT_CLASS}),
        }

    def clean(self):
        data = super().clean()
        if data.get("customer_type") == User.CustomerType.COMPANY and not data.get(
            "company_name"
        ):
            self.add_error("company_name", "Компанийн нэрийг бөглөнө үү")
        return data
