from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)
from django.contrib.auth.password_validation import validate_password

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
    class Meta:
        model = User
        fields = ("full_name", "phone")
        widgets = {
            "full_name": forms.TextInput(
                attrs={"class": "w-full rounded-md border border-gray-300 px-3 py-2"}
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "w-full rounded-md border border-gray-300 px-3 py-2",
                    "inputmode": "numeric",
                }
            ),
        }
