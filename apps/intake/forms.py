from django import forms
from django.forms import formset_factory

from apps.branches.models import Branch

from .models import DeviceCategory, DeviceItem, IntakeRequest

INPUT = "w-full rounded-md border border-gray-300 px-3 py-2 focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
SELECT = INPUT


class IntakeRequestForm(forms.ModelForm):
    """Step 4: contact + branch."""

    class Meta:
        model = IntakeRequest
        fields = (
            "customer_type",
            "contact_name",
            "company_name",
            "contact_phone",
            "contact_email",
            "city",
            "district",
            "address_line",
            "preferred_branch",
            "pickup_required",
            "pickup_lat",
            "pickup_lng",
        )
        widgets = {
            "customer_type": forms.Select(attrs={"class": SELECT}),
            "contact_name": forms.TextInput(attrs={"class": INPUT}),
            "company_name": forms.TextInput(attrs={"class": INPUT}),
            "contact_phone": forms.TextInput(
                attrs={"class": INPUT, "inputmode": "numeric", "placeholder": "99XX-XXXX"}
            ),
            "contact_email": forms.EmailInput(
                attrs={"class": INPUT, "inputmode": "email", "placeholder": "you@example.com"}
            ),
            "city": forms.TextInput(attrs={"class": INPUT}),
            "district": forms.TextInput(attrs={"class": INPUT}),
            "address_line": forms.TextInput(attrs={"class": INPUT}),
            "preferred_branch": forms.Select(attrs={"class": SELECT}),
            "pickup_lat": forms.HiddenInput(),
            "pickup_lng": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["preferred_branch"].queryset = Branch.objects.filter(is_active=True)
        self.fields["preferred_branch"].empty_label = "— Сонгоно уу —"
        self.fields["company_name"].required = False
        self.fields["contact_email"].required = False  # required only for guests (validated in view)

    def clean(self):
        data = super().clean()
        if data.get("customer_type") == IntakeRequest.CustomerType.COMPANY and not data.get(
            "company_name"
        ):
            self.add_error("company_name", "Компанийн нэрийг бөглөнө үү")
        return data


class DeviceItemForm(forms.ModelForm):
    """Step 1: device basics only — Ангилал, Бренд, Модель, IMEI, Дэлгэрэнгүй.

    Нөхцөл/тоо ширхэг зэрэг талбарууд хэрэглэгчээс асуухгүй; моделийн default
    утгаараа хадгалагдана.
    """

    class Meta:
        model = DeviceItem
        fields = (
            "category",
            "brand",
            "model",
            "imei_or_serial",
            "issue_description",
        )
        widgets = {
            # Ангилал солиход тухайн ангиллын брендүүд шүүгдэж харагдана (Alpine).
            "category": forms.Select(
                attrs={"class": SELECT, "x-on:change": "onCategory($event.target.value)"}
            ),
            "brand": forms.TextInput(attrs={"class": INPUT, "placeholder": "Брендээ бичнэ үү"}),
            "model": forms.TextInput(attrs={"class": INPUT, "placeholder": "iPhone 12, Galaxy S21"}),
            "imei_or_serial": forms.TextInput(
                attrs={"class": INPUT, "placeholder": "IMEI (заавал биш)"}
            ),
            "issue_description": forms.Textarea(
                attrs={"class": INPUT, "rows": 3, "placeholder": "Нэмэлт мэдээлэл, тайлбар..."}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = DeviceCategory.objects.filter(is_active=True)
        self.fields["category"].empty_label = "— Сонгоно уу —"
        self.fields["issue_description"].label = "Дэлгэрэнгүй"


# Нэг хүсэлтээр олон төхөөрөмж зарах боломжтой — динамик formset.
DeviceItemFormSet = formset_factory(
    DeviceItemForm, extra=1, min_num=1, validate_min=True, can_delete=False
)


class TrackingTokenForm(forms.Form):
    token = forms.CharField(
        label="Tracking код",
        max_length=64,
        widget=forms.TextInput(
            attrs={"class": INPUT, "placeholder": "12345678-..."}
        ),
    )
