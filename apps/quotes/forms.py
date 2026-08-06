from django import forms

from apps.accounts.models import User
from apps.intake.models import IntakeRequest

from .models import Pickup, Quotation

INPUT = "w-full rounded-md border border-gray-300 px-3 py-2 focus:border-brand-500 focus:ring-1 focus:ring-brand-500"


class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ("quoted_price_min", "quoted_price_max", "final_offer_price", "note", "valid_until")
        widgets = {
            "quoted_price_min": forms.NumberInput(attrs={"class": INPUT, "inputmode": "numeric"}),
            "quoted_price_max": forms.NumberInput(attrs={"class": INPUT, "inputmode": "numeric"}),
            "final_offer_price": forms.NumberInput(attrs={"class": INPUT, "inputmode": "numeric"}),
            "note": forms.Textarea(attrs={"class": INPUT, "rows": 3}),
            "valid_until": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
        }

    def clean(self):
        data = super().clean()
        mn = data.get("quoted_price_min")
        mx = data.get("quoted_price_max")
        if mn is not None and mx is not None and mn > mx:
            raise forms.ValidationError("Доод үнэ дээд үнээс их байж болохгүй.")
        return data


class StatusChangeForm(forms.Form):
    new_status = forms.ChoiceField(
        label="Шинэ төлөв",
        choices=IntakeRequest.Status.choices,
        widget=forms.Select(attrs={"class": INPUT}),
    )
    comment = forms.CharField(
        label="Тайлбар",
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT, "rows": 2}),
    )


class AssignForm(forms.Form):
    assigned_to = forms.ModelChoiceField(
        label="Хариуцах оператор",
        queryset=User.objects.filter(
            role__in=[User.Role.OPERATOR, User.Role.MANAGER, User.Role.ADMIN]
        ),
        widget=forms.Select(attrs={"class": INPUT}),
        required=False,
        empty_label="— Хувиарлаагүй —",
    )


class PickupForm(forms.ModelForm):
    class Meta:
        model = Pickup
        fields = (
            "pickup_date",
            "pickup_address",
            "assigned_staff",
            "actual_buy_price",
            "payment_status",
            "payment_method",
            "notes",
        )
        widgets = {
            "pickup_date": forms.DateTimeInput(
                attrs={"class": INPUT, "type": "datetime-local"}
            ),
            "pickup_address": forms.TextInput(attrs={"class": INPUT}),
            "assigned_staff": forms.Select(attrs={"class": INPUT}),
            "actual_buy_price": forms.NumberInput(attrs={"class": INPUT, "inputmode": "numeric"}),
            "payment_status": forms.Select(attrs={"class": INPUT}),
            "payment_method": forms.Select(attrs={"class": INPUT}),
            "notes": forms.Textarea(attrs={"class": INPUT, "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_staff"].queryset = User.objects.filter(
            role__in=[User.Role.OPERATOR, User.Role.MANAGER, User.Role.ADMIN]
        )
